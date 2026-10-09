"""Shared API contracts for the GhostOS backend."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ExtractionStatus = Literal["success", "empty", "skipped", "error"]
ClassificationCategory = Literal["invoice", "receipt", "other", "uncertain"]
DocumentKind = Literal[
    "receipt",
    "invoice",
    "statement",
    "identity_or_civil",
    "legal",
    "medical",
    "other",
    "uncertain",
]
FieldProfile = Literal["transaction", "reference", "none"]

_DOCUMENT_KIND_VALUES = frozenset(
    {
        "receipt",
        "invoice",
        "statement",
        "identity_or_civil",
        "legal",
        "medical",
        "other",
        "uncertain",
    }
)

# Model outputs are non-deterministic: the local model may emit a near-miss
# kind such as "quotation" or "bank_statement". Normalize those to the bounded
# enum so an advisory kind can never hard-fail the whole classification. Any
# unrecognized value maps to "other" (the safe non-transactional catch-all).
_DOCUMENT_KIND_ALIASES: dict[str, str] = {
    "quotation": "other",
    "quote": "other",
    "price_quotation": "other",
    "contract": "legal",
    "agreement": "legal",
    "lease": "legal",
    "court_order": "legal",
    "tax_return": "legal",
    "bank_statement": "statement",
    "card_statement": "statement",
    "account_statement": "statement",
    "birth_certificate": "identity_or_civil",
    "certificate": "identity_or_civil",
    "passport": "identity_or_civil",
    "identity": "identity_or_civil",
    "id": "identity_or_civil",
    "civil_record": "identity_or_civil",
    "prescription": "medical",
    "medical_record": "medical",
}


def normalize_document_kind(value: object) -> DocumentKind | None:
    """Map a model-supplied kind to the bounded enum, or ``None`` if absent.

    Returns ``None`` for missing/non-string values; canonical enum values pass
    through unchanged; unknown strings fall back to ``"other"`` rather than
    raising, so a mislabeled kind degrades to the non-transactional default
    instead of failing the classification.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    if key in _DOCUMENT_KIND_VALUES:
        return key  # type: ignore[return-value]
    return _DOCUMENT_KIND_ALIASES.get(key, "other")


def field_profile_for(document_kind: DocumentKind | None) -> FieldProfile:
    """Compatibility wrapper for the backend-owned awareness policy."""
    from app.services.document_awareness import derive_field_profile

    return derive_field_profile(document_kind)


class ScanRequest(BaseModel):
    """Request to scan a user-selected root path in a later phase."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"root_path": "sample-inbox"}],
        }
    )

    root_path: str = Field(..., min_length=1, description="Root path selected for scanning")


class FileRecord(BaseModel):
    """Backend-owned metadata and extraction result for one file."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_id": "file-001",
                    "relative_path": "receipts/coffee-shop.pdf",
                    "filename": "coffee-shop.pdf",
                    "extension": ".pdf",
                    "size_bytes": 24576,
                    "sha256": "a" * 64,
                    "extraction_status": "success",
                    "text_excerpt": "COFFEE SHOP RECEIPT\nTotal: PHP 185.00",
                    "reason": None,
                }
            ]
        }
    )

    file_id: str = Field(..., min_length=1)
    relative_path: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    extension: str = Field(..., min_length=1)
    size_bytes: int = Field(..., ge=0)
    sha256: str | None = None
    extraction_status: ExtractionStatus
    text_excerpt: str = Field(default="", max_length=2000)
    reason: str | None = None


class ScanResponse(BaseModel):
    """Response contract for a later backend scanning operation."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "root_path": "sample-inbox",
                    "total_files": 1,
                    "files": [
                        {
                            "file_id": "file-001",
                            "relative_path": "receipts/coffee-shop.pdf",
                            "filename": "coffee-shop.pdf",
                            "extension": ".pdf",
                            "size_bytes": 24576,
                            "sha256": "a" * 64,
                            "extraction_status": "success",
                            "text_excerpt": "COFFEE SHOP RECEIPT\nTotal: PHP 185.00",
                            "reason": None,
                        }
                    ],
                }
            ]
        }
    )

    root_path: str = Field(..., min_length=1)
    total_files: int = Field(..., ge=0)
    files: list[FileRecord]


class ClassificationRecord(BaseModel):
    """Structured, non-operational classification output from a local model."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "category": "receipt",
                    "document_kind": "receipt",
                    "merchant": "Coffee Shop",
                    "date": "2026-10-08",
                    "amount_text": "PHP 185.00",
                    "currency": "PHP",
                    "evidence_quote": "Total: PHP 185.00",
                    "explanation": "The document contains a merchant receipt total.",
                }
            ]
        }
    )

    category: ClassificationCategory
    document_kind: DocumentKind | None = None
    merchant: str | None = None
    date: str | None = None
    amount_text: str | None = None
    currency: str | None = None
    evidence_quote: str | None = None
    explanation: str | None = None

    @field_validator("document_kind", mode="before")
    @classmethod
    def _normalize_document_kind(cls, value: object) -> DocumentKind | None:
        return normalize_document_kind(value)

    @property
    def field_profile(self) -> FieldProfile:
        """Backend-derived editable-field profile (never supplied by the model)."""
        from app.services.document_awareness import derive_field_profile

        legacy_category = (
            self.category if "document_kind" not in self.model_fields_set else None
        )
        return derive_field_profile(self.document_kind, legacy_category=legacy_category)


class ProposedOperation(BaseModel):
    """Backend-generated preview of a possible file organization operation."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_id": "file-001",
                    "original_relative_path": "receipts/coffee-shop.pdf",
                    "destination_relative_path": "organized/receipts/coffee-shop.pdf",
                    "reason": "Classified as a receipt from Coffee Shop.",
                }
            ]
        }
    )

    file_id: str = Field(..., min_length=1)
    original_relative_path: str = Field(..., min_length=1)
    destination_relative_path: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class ClassifyRequest(BaseModel):
    """Request to classify one file's text excerpt using the local model."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_id": "file-001",
                    "text_excerpt": "COFFEE SHOP RECEIPT\nTotal: PHP 185.00",
                }
            ]
        }
    )

    file_id: str = Field(..., min_length=1, description="Backend-generated stable file identifier")
    text_excerpt: str = Field(..., min_length=1, max_length=8000, description="Bounded text excerpt from the file")


class ClassifyResponse(BaseModel):
    """Response associating a file_id with its classification and proposed operation."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_id": "file-001",
                    "classification": {
                        "category": "receipt",
                        "document_kind": "receipt",
                        "merchant": "Coffee Shop",
                        "date": "2026-10-08",
                        "amount_text": "PHP 185.00",
                        "currency": "PHP",
                        "evidence_quote": "Total: PHP 185.00",
                        "explanation": "The document contains a merchant receipt total.",
                    },
                    "field_profile": "transaction",
                    "proposed_operation": {
                        "file_id": "file-001",
                        "original_relative_path": "inbox/coffee.pdf",
                        "destination_relative_path": "organized/receipts/coffee.pdf",
                        "reason": "Classified as a receipt from Coffee Shop.",
                    },
                    "needs_review": False,
                    "review_reason": None,
                    "elapsed_seconds": 1.42,
                }
            ]
        }
    )

    file_id: str = Field(..., min_length=1)
    classification: ClassificationRecord
    field_profile: FieldProfile = "none"
    proposed_operation: ProposedOperation | None = None
    needs_review: bool = False
    review_reason: str | None = None
    elapsed_seconds: float = Field(..., ge=0)
