"""Unit tests for source-aware classification validation."""

from copy import deepcopy
from decimal import Decimal

import pytest

from app.schemas import ClassificationRecord
from app.services.classification_validation import validate_classification


def make_classification(**overrides: object) -> ClassificationRecord:
    values: dict[str, object] = {
        "category": "receipt",
        "merchant": "Coffee Shop",
        "date": "2026-10-09",
        "amount_text": "PHP 1,250.00",
        "currency": "PHP",
        "evidence_quote": "Total: PHP 1,250.00",
        "explanation": "Receipt with a total.",
    }
    values.update(overrides)
    return ClassificationRecord(**values)


def test_valid_invoice_with_exact_evidence_and_decimal_amount() -> None:
    source = "ACME INVOICE\nDate: 2026-10-09\nTotal: USD 42.50"
    classification = make_classification(
        category="invoice",
        merchant="ACME",
        date="2026-10-09",
        amount_text="USD 42.50",
        currency="USD",
        evidence_quote="Total: USD 42.50",
    )

    result = validate_classification(source, classification)

    assert result.is_valid is True
    assert result.needs_review is False
    assert result.flags == ()
    assert result.parsed_amount == Decimal("42.50")
    assert isinstance(result.parsed_amount, Decimal)


def test_valid_receipt_with_currency_symbol() -> None:
    source = "COFFEE SHOP RECEIPT\nTotal: ₱1,250.00"
    classification = make_classification(
        amount_text="₱1,250.00",
        currency="PHP",
        evidence_quote="Total: ₱1,250.00",
    )

    result = validate_classification(source, classification)

    assert result.is_valid is True
    assert result.parsed_amount == Decimal("1250.00")


def test_quote_not_in_source_is_invalid_and_requires_review() -> None:
    result = validate_classification(
        "COFFEE SHOP RECEIPT\nTotal: PHP 1,250.00",
        make_classification(evidence_quote="Total: PHP 999.00"),
    )

    assert result.is_valid is False
    assert result.needs_review is True
    assert result.flags == ("evidence_quote_not_found",)


@pytest.mark.parametrize("category", ["invoice", "receipt"])
def test_missing_evidence_for_invoice_or_receipt_requires_review(category: str) -> None:
    result = validate_classification(
        "Document with no quoted evidence",
        make_classification(category=category, evidence_quote=None, amount_text=None),
    )

    assert result.is_valid is True
    assert result.needs_review is True
    assert result.flags[:2] == ("missing_evidence_quote", "missing_amount")


def test_missing_amount_for_invoice_or_receipt_requires_review() -> None:
    result = validate_classification(
        "INVOICE\nMerchant: ACME\nDate: 2026-10-09",
        make_classification(category="invoice", amount_text=None, evidence_quote=None),
    )

    assert result.is_valid is True
    assert result.needs_review is True
    assert "missing_amount" in result.flags
    assert result.parsed_amount is None


def test_multiple_totals_are_flagged_even_when_amount_is_missing() -> None:
    result = validate_classification(
        "Subtotal: PHP 10.00\nTotal: PHP 12.00",
        make_classification(amount_text=None, evidence_quote="Total: PHP 12.00"),
    )

    assert result.is_valid is False
    assert result.needs_review is True
    assert result.flags == ("missing_amount", "ambiguous_amount")
    assert result.parsed_amount is None


@pytest.mark.parametrize(
    ("amount_text", "expected"),
    [
        ("1250.00", Decimal("1250.00")),
        ("1,250.00", Decimal("1250.00")),
        ("PHP 1,250.00", Decimal("1250.00")),
        ("₱1,250.00", Decimal("1250.00")),
        ("USD 42.50", Decimal("42.50")),
    ],
)
def test_supported_amount_formats_use_decimal(amount_text: str, expected: Decimal) -> None:
    result = validate_classification(
        f"Total: {amount_text}",
        make_classification(amount_text=amount_text, currency=None, evidence_quote=f"Total: {amount_text}"),
    )

    assert result.parsed_amount == expected
    assert isinstance(result.parsed_amount, Decimal)


@pytest.mark.parametrize("amount_text", ["-42.50", "0.00"])
def test_negative_and_zero_amounts_are_not_silently_altered(amount_text: str) -> None:
    result = validate_classification(
        f"Total: {amount_text}",
        make_classification(amount_text=amount_text, currency=None, evidence_quote=f"Total: {amount_text}"),
    )

    assert result.parsed_amount == Decimal(amount_text)


@pytest.mark.parametrize("amount_text", ["10-20", "about 20.00", "N/A", "not available"])
def test_ranges_approximate_and_malformed_amounts_are_invalid(amount_text: str) -> None:
    result = validate_classification(
        "Receipt with an amount",
        make_classification(amount_text=amount_text),
    )

    assert result.is_valid is False
    assert result.needs_review is True
    assert "invalid_amount_format" in result.flags
    assert result.parsed_amount is None


def test_multiple_totals_are_ambiguous_and_untrusted() -> None:
    source = "Subtotal: PHP 10.00\nTotal: PHP 12.00"
    result = validate_classification(source, make_classification(evidence_quote="Total: PHP 12.00"))

    assert result.is_valid is False
    assert result.needs_review is True
    assert "ambiguous_amount" in result.flags
    assert result.parsed_amount is None


def test_conflicting_classification_amount_is_ambiguous_and_untrusted() -> None:
    source = "Total: PHP 12.00"
    result = validate_classification(
        source,
        make_classification(amount_text="PHP 13.00", evidence_quote="Total: PHP 12.00"),
    )

    assert result.is_valid is False
    assert "ambiguous_amount" in result.flags
    assert result.parsed_amount is None


def test_currency_mismatch_requires_review_and_is_invalid() -> None:
    result = validate_classification(
        "Total: USD 42.50",
        make_classification(amount_text="USD 42.50", currency="PHP", evidence_quote="Total: USD 42.50"),
    )

    assert result.is_valid is False
    assert result.needs_review is True
    assert "currency_mismatch" in result.flags


def test_missing_currency_is_flagged_when_source_explicitly_has_currency() -> None:
    result = validate_classification(
        "Total: USD 42.50",
        make_classification(amount_text="42.50", currency=None, evidence_quote="Total: USD 42.50"),
    )

    assert result.is_valid is True
    assert result.needs_review is True
    assert "missing_currency" in result.flags


@pytest.mark.parametrize("field, flag", [("merchant", "missing_merchant"), ("date", "missing_date")])
def test_missing_merchant_or_date_requires_review(field: str, flag: str) -> None:
    result = validate_classification(
        "Total: PHP 1,250.00",
        make_classification(**{field: None}, evidence_quote="Total: PHP 1,250.00"),
    )

    assert result.is_valid is True
    assert result.needs_review is True
    assert flag in result.flags


def test_other_allows_nullable_context_without_independent_review() -> None:
    result = validate_classification(
        "A general document",
        make_classification(
            category="other",
            merchant=None,
            date=None,
            amount_text=None,
            currency=None,
            evidence_quote=None,
        ),
    )

    assert result.is_valid is True
    assert result.needs_review is False
    assert result.flags == ("missing_evidence_quote",)


def test_uncertain_always_requires_review() -> None:
    result = validate_classification(
        "Unclear document",
        make_classification(category="uncertain", evidence_quote=None, amount_text=None),
    )

    assert result.is_valid is True
    assert result.needs_review is True
    assert result.flags == ("missing_evidence_quote", "uncertain_classification")


def test_multiple_flags_have_stable_order_and_no_duplicates() -> None:
    result = validate_classification(
        "INVOICE",
        make_classification(
            category="invoice",
            merchant=None,
            date=None,
            amount_text="N/A",
            evidence_quote="missing",
        ),
    )

    assert result.flags == (
        "evidence_quote_not_found",
        "invalid_amount_format",
        "missing_merchant",
        "missing_date",
    )
    assert len(result.flags) == len(set(result.flags))


def test_classification_is_not_mutated() -> None:
    classification = make_classification()
    before = deepcopy(classification.model_dump())

    validate_classification("Total: PHP 1,250.00", classification)

    assert classification.model_dump() == before


@pytest.mark.parametrize("source_text", ["", "   ", "\n\t"])
def test_empty_source_text_is_handled_without_crashing(source_text: str) -> None:
    result = validate_classification(source_text, make_classification())

    assert result.is_valid is False
    assert result.needs_review is True
    assert "evidence_quote_not_found" in result.flags


def test_conflicting_values_never_return_trusted_amount() -> None:
    result = validate_classification(
        "Subtotal: USD 10.00\nTotal: USD 12.00",
        make_classification(
            amount_text="USD 12.00",
            currency="USD",
            evidence_quote="Total: USD 12.00",
        ),
    )

    assert "ambiguous_amount" in result.flags
    assert result.parsed_amount is None
