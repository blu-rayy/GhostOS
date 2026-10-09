"""Source-aware validation for model-generated classifications.

This module deliberately keeps validation metadata separate from
``ClassificationRecord``. ``is_valid`` describes hard validation checks:
evidence and supplied amounts must be trustworthy. ``needs_review`` indicates
that a human should inspect the result, including missing contextual fields
and uncertain classifications. Flags are emitted in a stable order and are
safe to map to UI messages.

The initial implementation uses exact evidence substring matching only. It
does not use fuzzy matching, infer amounts, or silently select a value from
multiple competing monetary values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.schemas import ClassificationRecord


@dataclass(frozen=True)
class ClassificationValidationResult:
    """Validation metadata kept separate from the model classification."""

    is_valid: bool
    needs_review: bool
    flags: tuple[str, ...]
    parsed_amount: Decimal | None


@dataclass(frozen=True)
class _AmountCandidate:
    amount: Decimal
    currency: str | None
    source_line: str
    label: str
    label_class: str


_SUPPORTED_CURRENCIES = {
    "PHP": "PHP",
    "₱": "PHP",
    "USD": "USD",
    "$": "USD",
    "EUR": "EUR",
    "€": "EUR",
    "GBP": "GBP",
    "£": "GBP",
    "SGD": "SGD",
    "S$": "SGD",
    "JPY": "JPY",
    "¥": "JPY",
}
_CURRENCY_TOKEN = r"(?:PHP|USD|EUR|GBP|SGD|JPY|₱|\$|€|£|¥)"
_NUMBER_TOKEN = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
_MONEY_TOKEN_RE = re.compile(
    rf"(?P<sign>-)?\s*(?P<currency>{_CURRENCY_TOKEN})?\s*(?P<number>{_NUMBER_TOKEN})",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(rf"(?<![A-Za-z])(?P<currency>{_CURRENCY_TOKEN})(?![A-Za-z])", re.IGNORECASE)
_AUTHORITATIVE_LABEL_RE = re.compile(
    r"(?P<label>"
    r"final[\s_]+total|total[\s_]+amount[\s_]+due|total[\s_]+due|"
    r"total[\s_]+payable|total[\s_]+paid|total[\s_]+charged|grand[\s_]+total|"
    r"invoice[\s_]+total|quoted[\s_]+total|statement[\s]+balance|"
    r"total[\s]+new[\s]+charges|balance[\s]+due|"
    r"(?<!minimum[ ])amount[\s]+due|\btotal\b"
    r")",
    re.IGNORECASE,
)
_COMPONENT_LABEL_RE = re.compile(
    r"^\s*(?P<label>subtotal|discount|less|vat|tax|service[\s]+fee|fee)\b",
    re.IGNORECASE,
)
_APPROXIMATE_RE = re.compile(r"(?:about|approx(?:imately)?|around|roughly|~)", re.IGNORECASE)
_QUOTATION_DOCUMENT_RE = re.compile(
    r"(?:\bquotation\b|\bquoted[\s_]+total\b|price\s+quotation|"
    r"not\s+a\s+request\s+for\s+payment)",
    re.IGNORECASE,
)

# Document kinds that are never a single transaction. For these the validator
# must not demand (or trust) merchant/date/amount/currency, and must always
# route them to human review rather than into the expense totals.
_NON_TRANSACTIONAL_KINDS = frozenset(
    {"statement", "identity_or_civil", "legal", "medical"}
)


def _canonical_currency(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return _SUPPORTED_CURRENCIES.get(normalized)


def _parse_single_amount(value: str) -> tuple[Decimal, str | None] | None:
    """Parse one supported amount without converting through float."""
    match = _MONEY_TOKEN_RE.fullmatch(value.strip())
    if match is None:
        return None
    number_text = match.group("number").replace(",", "")
    if "." not in number_text and number_text.startswith("0") and len(number_text) > 1:
        number_text = number_text.lstrip("0") or "0"
    try:
        amount = Decimal(f"{match.group('sign') or ''}{number_text}")
    except InvalidOperation:
        return None
    return amount, _canonical_currency(match.group("currency"))


def _source_currencies(source_text: str) -> set[str]:
    return {
        canonical
        for match in _CURRENCY_RE.finditer(source_text)
        if (canonical := _canonical_currency(match.group("currency"))) is not None
    }


def _line_amounts(line: str) -> list[tuple[Decimal, str | None]]:
    """Extract monetary-looking values without treating percentages as amounts."""
    amounts: list[tuple[Decimal, str | None]] = []
    for match in _MONEY_TOKEN_RE.finditer(line):
        number = match.group("number")
        if match.group("currency") is None and "." not in number and "," not in number:
            continue
        parsed = _parse_single_amount(match.group(0))
        if parsed is not None:
            amounts.append(parsed)
    return amounts


def _source_amount_candidates(
    source_text: str,
) -> tuple[list[_AmountCandidate], list[_AmountCandidate]]:
    """Return authoritative final candidates and explicit reconciliation components."""
    authoritative: list[_AmountCandidate] = []
    components: list[_AmountCandidate] = []
    for line in source_text.splitlines():
        authoritative_match = _AUTHORITATIVE_LABEL_RE.search(line)
        component_match = _COMPONENT_LABEL_RE.search(line)
        if authoritative_match is not None:
            label = authoritative_match.group("label").lower().replace("_", " ")
            for amount, currency in _line_amounts(line):
                authoritative.append(
                    _AmountCandidate(amount, currency, line, label, "authoritative")
                )
        elif component_match is not None:
            label = component_match.group("label").lower().replace("_", " ")
            for amount, currency in _line_amounts(line):
                if "discount" in label or label == "less":
                    amount = -abs(amount)
                components.append(
                    _AmountCandidate(amount, currency, line, label, "component")
                )

    # Repeated copies of the same label/value are safe to deduplicate. Values
    # under distinct labels remain separate, which keeps card statements
    # ambiguous even when two balances happen to be numerically equal.
    unique: dict[tuple[Decimal, str | None, str], _AmountCandidate] = {}
    for candidate in authoritative:
        key = (candidate.amount, candidate.currency, candidate.label)
        unique[key] = candidate
    return list(unique.values()), components


def _resolve_authoritative_amount(
    authoritative: list[_AmountCandidate],
    components: list[_AmountCandidate],
) -> Decimal | None:
    """Resolve one final amount only when labels and explicit arithmetic agree."""
    if len(authoritative) != 1:
        return None

    final_amount = authoritative[0].amount
    subtotals = [candidate.amount for candidate in components if candidate.label == "subtotal"]
    adjustments = [
        candidate.amount
        for candidate in components
        if candidate.label != "subtotal"
    ]
    if len(subtotals) > 1:
        return None
    if subtotals and subtotals[0] + sum(adjustments, Decimal("0")) != final_amount:
        return None
    return final_amount


def _append_flag(flags: list[str], flag: str) -> None:
    if flag not in flags:
        flags.append(flag)


def validate_classification(
    source_text: str,
    classification: ClassificationRecord,
) -> ClassificationValidationResult:
    """Validate a classification against its original extracted text.

    ``source_text`` should be the same bounded excerpt sent to
    :func:`app.services.local_ai.classify_excerpt`. The supplied classification
    is never mutated. Missing evidence always requires review. Explicit
    quotation markers also require review so a quotation cannot be accepted as
    an expense if the model labels it as an invoice or receipt.
    """
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    if not isinstance(classification, ClassificationRecord):
        raise TypeError("classification must be a ClassificationRecord")

    flags: list[str] = []
    is_valid = True
    needs_review = False
    category = classification.category
    required_context = category in {"invoice", "receipt"}

    evidence_quote = classification.evidence_quote
    if evidence_quote is None or not evidence_quote.strip():
        _append_flag(flags, "missing_evidence_quote")
        needs_review = True
    elif evidence_quote not in source_text:
        _append_flag(flags, "evidence_quote_not_found")
        is_valid = False
        needs_review = True

    authoritative_candidates, component_candidates = _source_amount_candidates(source_text)
    authoritative_amount = _resolve_authoritative_amount(
        authoritative_candidates,
        component_candidates,
    )
    parsed_amount: Decimal | None = None
    classification_amount = classification.amount_text
    parsed_classification: tuple[Decimal, str | None] | None = None

    if classification_amount is None or not classification_amount.strip():
        if required_context:
            _append_flag(flags, "missing_amount")
            needs_review = True
    else:
        if _APPROXIMATE_RE.search(classification_amount) or "-" in classification_amount.strip().lstrip("-"):
            parsed = None
        else:
            parsed = _parse_single_amount(classification_amount)
        if parsed is None:
            _append_flag(flags, "invalid_amount_format")
            is_valid = False
            needs_review = True
        else:
            parsed_classification = parsed
            parsed_amount, amount_currency = parsed

    if authoritative_amount is None and authoritative_candidates:
        _append_flag(flags, "ambiguous_amount")
        parsed_amount = None
        is_valid = False
        needs_review = True
    elif (
        parsed_classification is not None
        and authoritative_amount is None
    ):
        _append_flag(flags, "ambiguous_amount")
        parsed_amount = None
        is_valid = False
        needs_review = True
    elif (
        parsed_classification is not None
        and authoritative_amount is not None
        and authoritative_amount != parsed_classification[0]
    ):
        _append_flag(flags, "ambiguous_amount")
        parsed_amount = None
        is_valid = False
        needs_review = True
    elif parsed_classification is not None:
        parsed_amount = parsed_classification[0]

    source_currencies = _source_currencies(source_text)
    declared_currency = _canonical_currency(classification.currency)
    amount_currency = parsed_classification[1] if parsed_classification is not None else None
    if classification.currency is not None and declared_currency is None:
        _append_flag(flags, "invalid_currency")
        is_valid = False
        needs_review = True
    elif source_currencies and declared_currency is None and amount_currency is None:
        _append_flag(flags, "missing_currency")
        needs_review = True
    elif declared_currency and source_currencies and declared_currency not in source_currencies:
        _append_flag(flags, "currency_mismatch")
        is_valid = False
        needs_review = True
    elif amount_currency and declared_currency and amount_currency != declared_currency:
        _append_flag(flags, "currency_mismatch")
        is_valid = False
        needs_review = True

    if required_context and (classification.merchant is None or not classification.merchant.strip()):
        _append_flag(flags, "missing_merchant")
        needs_review = True
    if required_context and (classification.date is None or not classification.date.strip()):
        _append_flag(flags, "missing_date")
        needs_review = True
    if category == "uncertain":
        _append_flag(flags, "uncertain_classification")
        needs_review = True
    if _QUOTATION_DOCUMENT_RE.search(source_text):
        _append_flag(flags, "quotation_document")
        needs_review = True

    # Non-transactional papers (statements, civil/identity records, legal and
    # medical documents) are never a single expense. They must always be
    # reviewed, and the model must not invent merchant/date/amount/currency to
    # fit the transaction schema.
    document_kind = classification.document_kind
    if document_kind in _NON_TRANSACTIONAL_KINDS:
        _append_flag(flags, "non_transactional_document")
        needs_review = True
        if any(
            getattr(classification, field) is not None
            for field in ("merchant", "date", "amount_text", "currency")
        ):
            _append_flag(flags, "transaction_fields_on_non_transactional")
            is_valid = False
            parsed_amount = None
    elif document_kind == "uncertain" or (
        document_kind is None
        and "document_kind" in classification.model_fields_set
    ):
        _append_flag(flags, "uncertain_document_kind")
        needs_review = True

    return ClassificationValidationResult(
        is_valid=is_valid,
        needs_review=needs_review,
        flags=tuple(flags),
        parsed_amount=parsed_amount,
    )
