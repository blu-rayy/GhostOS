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


_SUPPORTED_CURRENCIES = {
    "PHP": "PHP",
    "₱": "PHP",
    "USD": "USD",
    "$": "USD",
    "EUR": "EUR",
    "€": "EUR",
    "GBP": "GBP",
    "£": "GBP",
}
_CURRENCY_TOKEN = r"(?:PHP|USD|EUR|GBP|₱|\$|€|£)"
_NUMBER_TOKEN = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
_MONEY_TOKEN_RE = re.compile(
    rf"(?P<sign>-)?\s*(?P<currency>{_CURRENCY_TOKEN})?\s*(?P<number>{_NUMBER_TOKEN})",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(rf"(?<![A-Za-z])(?P<currency>{_CURRENCY_TOKEN})(?![A-Za-z])", re.IGNORECASE)
_TOTAL_CONTEXT_RE = re.compile(
    r"\b(?:total|subtotal|grand\s+total|amount\s+due|balance\s+due|amount\s+payable|payable)\b",
    re.IGNORECASE,
)
_APPROXIMATE_RE = re.compile(r"(?:about|approx(?:imately)?|around|roughly|~)", re.IGNORECASE)


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


def _source_total_candidates(source_text: str) -> list[tuple[Decimal, str | None]]:
    candidates: list[tuple[Decimal, str | None]] = []
    for line in source_text.splitlines():
        if not _TOTAL_CONTEXT_RE.search(line):
            continue
        for match in _MONEY_TOKEN_RE.finditer(line):
            parsed = _parse_single_amount(match.group(0))
            if parsed is not None:
                candidates.append(parsed)
    return candidates


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
    is never mutated. For ``other``, a missing evidence quote is reported but
    does not independently require review; ``invoice`` and ``receipt`` do
    require review when evidence is missing. ``uncertain`` always requires
    review.
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
        if required_context:
            needs_review = True
    elif evidence_quote not in source_text:
        _append_flag(flags, "evidence_quote_not_found")
        is_valid = False
        needs_review = True

    source_candidates = _source_total_candidates(source_text)
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

    if len(source_candidates) > 1:
        _append_flag(flags, "ambiguous_amount")
        parsed_amount = None
        is_valid = False
        needs_review = True
    elif (
        parsed_classification is not None
        and len(source_candidates) == 1
        and source_candidates[0][0] != parsed_classification[0]
    ):
        _append_flag(flags, "ambiguous_amount")
        parsed_amount = None
        is_valid = False
        needs_review = True

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

    return ClassificationValidationResult(
        is_valid=is_valid,
        needs_review=needs_review,
        flags=tuple(flags),
        parsed_amount=parsed_amount,
    )
