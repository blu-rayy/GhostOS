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
) -> DocumentKind | None:
    """Return a stored kind, with a fallback only for legacy records.

    A present-but-null ``document_kind`` is an explicit document-aware value
    and therefore derives the conservative ``none`` profile. Only records
    that predate this field receive category-based compatibility behavior.
    """
    if "document_kind" in classification:
        return normalize_document_kind(classification.get("document_kind"))

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
    legacy_category = None if "document_kind" in classification else classification.get("category")
    return derive_field_profile(kind, legacy_category=legacy_category)  # type: ignore[arg-type]
