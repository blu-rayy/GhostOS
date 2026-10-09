"""Backend-owned document-kind and editable-field policy."""

from __future__ import annotations

from typing import Mapping

from app.schemas import (
    ClassificationCategory,
    DocumentKind,
    FieldProfile,
    normalize_document_kind,
)


def document_kind_for_classification(
    classification: Mapping[str, object],
) -> DocumentKind:
    """Return a safe kind, including a compatibility fallback for old records."""
    explicit = normalize_document_kind(classification.get("document_kind"))
    if explicit is not None:
        return explicit

    category = classification.get("category")
    if category in {"receipt", "invoice", "other", "uncertain"}:
        return category  # type: ignore[return-value]
    return "uncertain"


def derive_field_profile(
    document_kind: DocumentKind | None,
    *,
    legacy_category: ClassificationCategory | None = None,
) -> FieldProfile:
    """Derive editable fields in code; never accept a model/client allowlist."""
    if document_kind in {"receipt", "invoice"}:
        return "transaction"
    if document_kind == "statement":
        return "reference"
    if document_kind is None and legacy_category in {"receipt", "invoice"}:
        return "transaction"
    return "none"


def field_profile_for_classification(
    classification: Mapping[str, object],
) -> FieldProfile:
    """Resolve legacy records and derive their backend-owned field profile."""
    kind = document_kind_for_classification(classification)
    return derive_field_profile(kind, legacy_category=classification.get("category"))  # type: ignore[arg-type]
