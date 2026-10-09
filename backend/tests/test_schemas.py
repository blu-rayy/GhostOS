"""Tests for Phase 1 shared API contracts."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas import (
    ClassificationRecord,
    FileRecord,
    ProposedOperation,
    ScanRequest,
    ScanResponse,
)
from app.services.document_awareness import derive_field_profile, field_profile_for_classification


client = TestClient(app)


def make_file_record(**overrides: object) -> FileRecord:
    values: dict[str, object] = {
        "file_id": "file-001",
        "relative_path": "receipts/coffee-shop.pdf",
        "filename": "coffee-shop.pdf",
        "extension": ".pdf",
        "size_bytes": 24576,
        "sha256": None,
        "extraction_status": "success",
        "text_excerpt": "Total: PHP 185.00",
        "reason": None,
    }
    values.update(overrides)
    return FileRecord(**values)


def test_valid_scan_request_and_response_construction() -> None:
    request = ScanRequest(root_path="sample-inbox")
    response = ScanResponse(
        root_path=request.root_path,
        total_files=1,
        files=[make_file_record()],
    )

    assert request.root_path == "sample-inbox"
    assert response.total_files == 1
    assert response.files[0].relative_path == "receipts/coffee-shop.pdf"


def test_negative_file_size_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_file_record(size_bytes=-1)


def test_invalid_category_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClassificationRecord(category="spam")


def test_unknown_document_kind_is_normalized_not_rejected() -> None:
    # The local model may emit near-miss kinds; they normalize to the bounded
    # enum rather than failing the whole classification.
    assert ClassificationRecord(category="other", document_kind="quotation").document_kind == "other"
    assert ClassificationRecord(category="other", document_kind="bank_statement").document_kind == "statement"
    assert ClassificationRecord(category="other", document_kind="birth_certificate").document_kind == "identity_or_civil"
    # Totally unknown strings degrade to the safe non-transactional catch-all.
    assert ClassificationRecord(category="other", document_kind="definitely_not_a_kind").document_kind == "other"


def test_document_kind_derives_field_profile() -> None:
    assert ClassificationRecord(category="receipt", document_kind="receipt").field_profile == "transaction"
    assert ClassificationRecord(category="invoice", document_kind="invoice").field_profile == "transaction"
    assert ClassificationRecord(category="other", document_kind="statement").field_profile == "reference"
    assert ClassificationRecord(category="other", document_kind="identity_or_civil").field_profile == "none"
    assert ClassificationRecord(category="other", document_kind="legal").field_profile == "none"
    assert ClassificationRecord(category="other", document_kind="medical").field_profile == "none"
    assert ClassificationRecord(category="other").field_profile == "none"
    assert ClassificationRecord(category="receipt").field_profile == "transaction"
    assert ClassificationRecord(category="receipt", document_kind=None).field_profile == "none"


@pytest.mark.parametrize(
    ("kind", "profile"),
    [
        ("receipt", "transaction"),
        ("invoice", "transaction"),
        ("statement", "reference"),
        ("identity_or_civil", "none"),
        ("legal", "none"),
        ("medical", "none"),
        ("other", "none"),
        ("uncertain", "none"),
    ],
)
def test_backend_profile_derivation_is_bounded(kind: str, profile: str) -> None:
    assert derive_field_profile(kind) == profile


def test_legacy_classification_uses_category_compatibility_fallback() -> None:
    assert field_profile_for_classification({"category": "receipt"}) == "transaction"
    assert field_profile_for_classification({"category": "other"}) == "none"


def test_field_profile_is_not_a_model_supplied_field() -> None:
    # field_profile is derived backend-side; the model cannot set it.
    with pytest.raises(ValidationError):
        ClassificationRecord(category="receipt", field_profile="transaction")


def test_extraction_status_is_restricted() -> None:
    with pytest.raises(ValidationError):
        make_file_record(extraction_status="unknown")


def test_invoice_classification_is_accepted() -> None:
    classification = ClassificationRecord(
        category="invoice",
        merchant="Acme Supplies",
        date="2026-10-09",
        amount_text="PHP 1,250.00",
        currency="PHP",
        evidence_quote="Invoice total PHP 1,250.00",
        explanation="The document is an invoice from a supplier.",
    )

    assert classification.category == "invoice"
    assert classification.merchant == "Acme Supplies"


def test_receipt_with_omitted_optional_fields_is_accepted() -> None:
    classification = ClassificationRecord(category="receipt")

    assert classification.category == "receipt"
    assert classification.merchant is None
    assert classification.explanation is None


def test_other_classification_is_accepted() -> None:
    classification = ClassificationRecord(category="other")

    assert classification.category == "other"


def test_uncertain_classification_is_accepted() -> None:
    classification = ClassificationRecord(
        category="uncertain",
        explanation="The document does not contain enough evidence.",
    )

    assert classification.category == "uncertain"


@pytest.mark.parametrize("unexpected_field", ["source_id", "file_id", "destination_relative_path"])
def test_unexpected_classification_fields_are_rejected(unexpected_field: str) -> None:
    with pytest.raises(ValidationError):
        ClassificationRecord(category="receipt", **{unexpected_field: "not-model-output"})


def test_classification_json_schema_contains_only_approved_properties() -> None:
    schema = ClassificationRecord.model_json_schema()
    properties = set(schema["properties"])
    approved = {
        "category",
        "document_kind",
        "merchant",
        "date",
        "amount_text",
        "currency",
        "evidence_quote",
        "explanation",
    }

    assert properties == approved
    assert schema["additionalProperties"] is False


def test_proposed_operation_contains_expected_fields() -> None:
    operation = ProposedOperation(
        file_id="file-001",
        original_relative_path="receipts/coffee-shop.pdf",
        destination_relative_path="organized/receipts/coffee-shop.pdf",
        reason="Receipt classification",
    )

    assert operation.file_id == "file-001"
    assert operation.destination_relative_path == "organized/receipts/coffee-shop.pdf"


def test_root_endpoint_still_works() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"app": "GhostOS", "status": "running", "phase": 1}


def test_contract_examples_endpoint_returns_valid_example_data() -> None:
    response = client.get("/api/contracts/examples")

    assert response.status_code == 200
    payload = response.json()
    assert ScanRequest.model_validate(payload["scan_request"])
    assert ScanResponse.model_validate(payload["scan_response"])
    assert ClassificationRecord.model_validate(payload["classification_record"])
    assert ProposedOperation.model_validate(payload["proposed_operation"])
    assert not payload["proposed_operation"]["destination_relative_path"].startswith(("/", "C:"))
    examples = payload["document_aware_examples"]
    assert examples["receipt"]["field_profile"] == "transaction"
    assert examples["bank_statement"]["classification"]["document_kind"] == "statement"
    assert examples["bank_statement"]["field_profile"] == "reference"
    assert examples["bank_statement"]["expense_by_default"] is False
    assert examples["birth_certificate"]["classification"]["document_kind"] == "identity_or_civil"
    assert examples["birth_certificate"]["field_profile"] == "none"
    assert examples["birth_certificate"]["transaction_correction_fields"] == []
