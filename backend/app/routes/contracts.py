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
    statement = ClassificationRecord(
        category="other",
        document_kind="statement",
        evidence_quote="Account statement for September 2026",
        explanation="The document contains multiple account transactions, not one expense.",
    )
    birth_certificate = ClassificationRecord(
        category="other",
        document_kind="identity_or_civil",
        evidence_quote="Certificate of Live Birth",
        explanation="Civil record with no transaction fields.",
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
        "document_aware_examples": {
            "receipt": {
                "classification": classification.model_dump(),
                "field_profile": classification.field_profile,
            },
            "bank_statement": {
                "classification": statement.model_dump(),
                "field_profile": statement.field_profile,
                "expense_by_default": False,
            },
            "birth_certificate": {
                "classification": birth_certificate.model_dump(),
                "field_profile": birth_certificate.field_profile,
                "transaction_correction_fields": [],
            },
        },
        "proposed_operation": operation.model_dump(),
    }
