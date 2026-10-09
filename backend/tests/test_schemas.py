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


def test_extraction_status_is_restricted() -> None:
    with pytest.raises(ValidationError):
        make_file_record(extraction_status="unknown")


def test_nullable_classification_fields_are_accepted() -> None:
    classification = ClassificationRecord(
        category="uncertain",
        merchant=None,
        date=None,
        amount_text=None,
        currency=None,
        evidence_quote=None,
        explanation=None,
    )

    assert classification.merchant is None
    assert classification.explanation is None


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
