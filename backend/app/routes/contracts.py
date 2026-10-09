"""Development-only endpoints for inspecting shared API contracts."""

from fastapi import APIRouter

from app.schemas import (
    ClassificationRecord,
    FileRecord,
    ProposedOperation,
    ScanRequest,
    ScanResponse,
)


router = APIRouter(prefix="/api/contracts", tags=["contracts"])


@router.get("/examples")
def contract_examples() -> dict[str, object]:
    """Return valid examples without scanning, calling Ollama, or writing files."""
    scan_request = ScanRequest(root_path="sample-inbox")
    file_record = FileRecord(
        file_id="file-001",
        relative_path="receipts/coffee-shop.pdf",
        filename="coffee-shop.pdf",
        extension=".pdf",
        size_bytes=24576,
        sha256="a" * 64,
        extraction_status="success",
        text_excerpt="COFFEE SHOP RECEIPT\nTotal: PHP 185.00",
    )
    scan_response = ScanResponse(
        root_path=scan_request.root_path,
        total_files=1,
        files=[file_record],
    )
    classification = ClassificationRecord(
        category="receipt",
        document_kind="receipt",
        merchant="Coffee Shop",
        date="2026-10-08",
        amount_text="PHP 185.00",
        currency="PHP",
        evidence_quote="Total: PHP 185.00",
        explanation="The document contains a merchant receipt total.",
    )
    operation = ProposedOperation(
        file_id=file_record.file_id,
        original_relative_path=file_record.relative_path,
        destination_relative_path="organized/receipts/coffee-shop.pdf",
        reason="Classified as a receipt from Coffee Shop.",
    )
    return {
        "scan_request": scan_request.model_dump(),
        "scan_response": scan_response.model_dump(),
        "classification_record": classification.model_dump(),
        "proposed_operation": operation.model_dump(),
    }
