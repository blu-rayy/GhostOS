"""Shared API contracts for the GhostOS backend."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ExtractionStatus = Literal["success", "empty", "skipped", "error"]
ClassificationCategory = Literal["invoice", "receipt", "other", "uncertain"]


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
    merchant: str | None = None
    date: str | None = None
    amount_text: str | None = None
    currency: str | None = None
    evidence_quote: str | None = None
    explanation: str | None = None


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
