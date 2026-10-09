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


@pytest.mark.parametrize(
    ("currency", "amount_text", "expected_amount"),
    [
        ("SGD", "SGD 380.00", Decimal("380.00")),
        ("JPY", "JPY 48,000", Decimal("48000")),
    ],
)
def test_valid_ground_truth_currencies_use_decimal(
    currency: str, amount_text: str, expected_amount: Decimal
) -> None:
    source = f"INVOICE\nTotal payable: {amount_text}"
    result = validate_classification(
        source,
        make_classification(
            category="invoice",
            amount_text=amount_text,
            currency=currency,
            evidence_quote=f"Total payable: {amount_text}",
        ),
    )

    assert result.is_valid is True
    assert result.needs_review is False
    assert result.flags == ()
    assert result.parsed_amount == expected_amount
    assert isinstance(result.parsed_amount, Decimal)


@pytest.mark.parametrize("currency", ["PHP", "USD", "EUR", "GBP"])
def test_existing_supported_currency_codes_remain_valid(currency: str) -> None:
    source = f"INVOICE\nTotal: {currency} 42.50"
    result = validate_classification(
        source,
        make_classification(
            category="invoice",
            amount_text=f"{currency} 42.50",
            currency=currency,
            evidence_quote=f"Total: {currency} 42.50",
        ),
    )

    assert result.is_valid is True
    assert result.needs_review is False
    assert result.flags == ()
    assert result.parsed_amount == Decimal("42.50")


def test_missing_sgd_currency_is_flagged_when_source_has_currency_evidence() -> None:
    result = validate_classification(
        "Receipt\nTotal paid: SGD 380.00",
        make_classification(
            amount_text="380.00",
            currency=None,
            evidence_quote="Total paid: SGD 380.00",
        ),
    )

    assert result.is_valid is True
    assert result.needs_review is True
    assert result.flags == ("missing_currency",)
    assert result.parsed_amount == Decimal("380.00")


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


def test_pixelforge_reconciled_final_total_is_authoritative() -> None:
    source = (
        "Subtotal: PHP 18,500.00\n"
        "Less 10% loyalty discount: -PHP 1,850.00\n"
        "Net of discount: PHP 16,650.00\n"
        "VAT 12%: PHP 1,998.00\n"
        "Total Amount Due: PHP 18,648.00"
    )
    result = validate_classification(
        source,
        make_classification(
            category="invoice",
            amount_text="PHP 18,648.00",
            currency="PHP",
            evidence_quote="Total Amount Due: PHP 18,648.00",
        ),
    )

    assert result.parsed_amount == Decimal("18648.00")
    assert result.is_valid is True
    assert result.needs_review is False
    assert "ambiguous_amount" not in result.flags


def test_sunbeam_reconciled_final_total_is_authoritative() -> None:
    source = "Subtotal: PHP 610.00\nVAT 12%: PHP 73.20\nFINAL TOTAL: PHP 683.20"
    result = validate_classification(
        source,
        make_classification(
            amount_text="PHP 683.20",
            currency="PHP",
            evidence_quote="FINAL TOTAL: PHP 683.20",
        ),
    )

    assert result.parsed_amount == Decimal("683.20")
    assert result.is_valid is True
    assert result.needs_review is False
    assert "ambiguous_amount" not in result.flags


def test_bayside_unreconciled_amount_due_remains_ambiguous() -> None:
    source = "Subtotal: PHP 1,250.00\nAMOUNT DUE: PHP 1,520.00"
    result = validate_classification(
        source,
        make_classification(
            amount_text="PHP 1,520.00",
            currency="PHP",
            evidence_quote="AMOUNT DUE: PHP 1,520.00",
        ),
    )

    assert result.parsed_amount is None
    assert result.is_valid is False
    assert result.needs_review is True
    assert "ambiguous_amount" in result.flags


def test_card_statement_distinct_balances_remain_ambiguous() -> None:
    source = (
        "Total new charges: PHP 5,391.06\n"
        "Statement balance: PHP 5,391.06\n"
        "Minimum amount due: PHP 850.00"
    )
    result = validate_classification(
        source,
        make_classification(
            category="uncertain",
            amount_text="PHP 5,391.06",
            currency="PHP",
            evidence_quote="Statement balance: PHP 5,391.06",
        ),
    )

    assert result.parsed_amount is None
    assert result.is_valid is False
    assert result.needs_review is True
    assert "ambiguous_amount" in result.flags


def test_aircon_amount_without_authoritative_total_is_not_trusted() -> None:
    source = "Paid the technician 1,500, then 1,800 with a freon top-up."
    result = validate_classification(
        source,
        make_classification(
            category="uncertain",
            amount_text="PHP 1,500.00",
            currency="PHP",
            evidence_quote="Paid the technician 1,500",
        ),
    )

    assert result.parsed_amount is None
    assert result.is_valid is False
    assert result.needs_review is True
    assert "ambiguous_amount" in result.flags


def test_currency_bearing_rate_without_final_total_is_not_trusted() -> None:
    source = "Translation rate: JPY 12 per character"
    result = validate_classification(
        source,
        make_classification(
            category="invoice",
            amount_text="JPY 12",
            currency="JPY",
            evidence_quote="Translation rate: JPY 12 per character",
        ),
    )

    assert result.parsed_amount is None
    assert result.is_valid is False
    assert result.needs_review is True
    assert "ambiguous_amount" in result.flags


def test_single_final_total_is_preferred_over_unrelated_line_items() -> None:
    source = "Item A: PHP 10.00\nItem B: PHP 20.00\nFINAL TOTAL: PHP 30.00"
    result = validate_classification(
        source,
        make_classification(
            amount_text="PHP 30.00",
            currency="PHP",
            evidence_quote="FINAL TOTAL: PHP 30.00",
        ),
    )

    assert result.parsed_amount == Decimal("30.00")
    assert result.is_valid is True
    assert result.needs_review is False
    assert "ambiguous_amount" not in result.flags


def test_missing_model_amount_is_not_filled_from_authoritative_total() -> None:
    result = validate_classification(
        "FINAL TOTAL: PHP 30.00",
        make_classification(amount_text=None, evidence_quote="FINAL TOTAL: PHP 30.00"),
    )

    assert result.parsed_amount is None
    assert result.is_valid is True
    assert result.needs_review is True
    assert "missing_amount" in result.flags


def test_malformed_model_amount_remains_invalid() -> None:
    result = validate_classification(
        "FINAL TOTAL: PHP 30.00",
        make_classification(amount_text="about PHP 30.00", evidence_quote="FINAL TOTAL: PHP 30.00"),
    )

    assert result.parsed_amount is None
    assert result.is_valid is False
    assert result.needs_review is True
    assert "invalid_amount_format" in result.flags


def test_model_amount_disagreeing_with_final_total_is_untrusted() -> None:
    result = validate_classification(
        "FINAL TOTAL: PHP 30.00",
        make_classification(amount_text="PHP 31.00", evidence_quote="FINAL TOTAL: PHP 30.00"),
    )

    assert result.parsed_amount is None
    assert result.is_valid is False
    assert result.needs_review is True
    assert "ambiguous_amount" in result.flags


def test_multiple_distinct_final_totals_remain_ambiguous() -> None:
    result = validate_classification(
        "TOTAL DUE: USD 30.00\nFINAL TOTAL: USD 31.00",
        make_classification(
            category="invoice",
            amount_text="USD 31.00",
            currency="USD",
            evidence_quote="FINAL TOTAL: USD 31.00",
        ),
    )

    assert result.parsed_amount is None
    assert result.is_valid is False
    assert result.needs_review is True
    assert "ambiguous_amount" in result.flags


@pytest.mark.parametrize("currency", ["PHP", "USD", "EUR", "GBP", "SGD", "JPY"])
def test_supported_currency_codes_work_on_authoritative_totals(currency: str) -> None:
    source = f"TOTAL PAYABLE: {currency} 42.50"
    result = validate_classification(
        source,
        make_classification(
            category="invoice",
            amount_text=f"{currency} 42.50",
            currency=currency,
            evidence_quote=source,
        ),
    )

    assert result.parsed_amount == Decimal("42.50")
    assert result.is_valid is True
    assert result.needs_review is False


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


def test_other_missing_evidence_requires_review() -> None:
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
    assert result.needs_review is True
    assert result.flags == ("missing_evidence_quote",)


def test_quotation_requires_review_even_when_amount_is_clear() -> None:
    source = (
        "document_type,Quotation\n"
        "vendor,Silverline Signage\n"
        "quoted_total,,,12500.00\n"
        "note,This is a price quotation only and not a request for payment."
    )
    result = validate_classification(
        source,
        make_classification(
            category="other",
            merchant="Silverline Signage",
            date="2026-09-29",
            amount_text="12500.00",
            currency="PHP",
            evidence_quote="quoted_total,,,12500.00",
        ),
    )

    assert result.parsed_amount == Decimal("12500.00")
    assert result.is_valid is True
    assert result.needs_review is True
    assert result.flags == ("quotation_document",)


def test_mislabeled_quotation_cannot_be_accepted_as_expense() -> None:
    source = "Quotation\nquoted_total,,,12500.00\nnot a request for payment"
    result = validate_classification(
        source,
        make_classification(
            category="invoice",
            amount_text="12500.00",
            currency="PHP",
            evidence_quote="quoted_total,,,12500.00",
        ),
    )

    assert result.parsed_amount == Decimal("12500.00")
    assert result.is_valid is True
    assert result.needs_review is True
    assert "quotation_document" in result.flags


def test_legitimate_non_expense_amount_without_quotation_marker_is_not_forced_to_review() -> None:
    result = validate_classification(
        "SERVICES AGREEMENT\nMonthly retainer: PHP 25,000.00",
        make_classification(
            category="other",
            amount_text=None,
            currency="PHP",
            evidence_quote="Monthly retainer: PHP 25,000.00",
        ),
    )

    assert result.parsed_amount is None
    assert result.is_valid is True
    assert result.needs_review is False
    assert result.flags == ()


def test_uncertain_always_requires_review() -> None:
    result = validate_classification(
        "Unclear document",
        make_classification(category="uncertain", evidence_quote=None, amount_text=None),
    )

    assert result.is_valid is True
    assert result.needs_review is True
    assert result.flags == ("missing_evidence_quote", "uncertain_classification")


@pytest.mark.parametrize("document_kind", ["statement", "identity_or_civil", "legal", "medical"])
def test_non_transactional_document_kind_always_requires_review(document_kind: str) -> None:
    result = validate_classification(
        "CERTIFICATE OF LIVE BIRTH\nName: MARA VILLANUEVA\nDate of birth: 1995-04-02",
        make_classification(
            category="other",
            document_kind=document_kind,
            merchant=None,
            date=None,
            amount_text=None,
            currency=None,
            evidence_quote="CERTIFICATE OF LIVE BIRTH",
        ),
    )

    assert result.needs_review is True
    assert "non_transactional_document" in result.flags
    # No transaction fields were supplied, so no fabricated-value flag.
    assert "transaction_fields_on_non_transactional" not in result.flags


def test_non_transactional_document_with_invented_transaction_fields_is_untrusted() -> None:
    result = validate_classification(
        "CERTIFICATE OF LIVE BIRTH\nName: MARA VILLANUEVA",
        make_classification(
            category="other",
            document_kind="identity_or_civil",
            merchant="Civil Registry",
            date="2026-10-09",
            amount_text="PHP 1.00",
            currency="PHP",
            evidence_quote="CERTIFICATE OF LIVE BIRTH",
        ),
    )

    assert result.is_valid is False
    assert result.needs_review is True
    assert "non_transactional_document" in result.flags
    assert "transaction_fields_on_non_transactional" in result.flags
    assert result.parsed_amount is None


def test_statement_without_invented_fields_requires_review_but_keeps_no_amount() -> None:
    result = validate_classification(
        "HARBOR FEDERAL BANK\nCredit Card Statement\nStatement balance: PHP 5,391.06",
        make_classification(
            category="other",
            document_kind="statement",
            merchant=None,
            date=None,
            amount_text=None,
            currency=None,
            evidence_quote="Statement balance: PHP 5,391.06",
        ),
    )

    assert result.needs_review is True
    assert "non_transactional_document" in result.flags
    assert result.parsed_amount is None


def test_uncertain_document_kind_requires_review() -> None:
    result = validate_classification(
        "Unclear document",
        make_classification(
            category="other",
            document_kind="uncertain",
            evidence_quote=None,
            amount_text=None,
        ),
    )

    assert result.needs_review is True
    assert "uncertain_document_kind" in result.flags


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
