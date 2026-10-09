"""Backend-driven proposed operation generator.

The backend — not Ollama — decides destination paths using fixed,
category-based rules. Ollama produces only a ClassificationRecord;
it never generates file paths or executable operations.
"""

from app.schemas import ClassificationRecord, ClassificationCategory, ProposedOperation
from app.services.document_awareness import field_profile_for_classification

# Fixed destination folders keyed by category.
# These rules are owned entirely by the backend.
_CATEGORY_DESTINATION: dict[ClassificationCategory, str] = {
    "invoice": "organized/invoices",
    "receipt": "organized/receipts",
    "other": "organized/other",
    # "uncertain" intentionally omitted — those always need human review.
}

_REVIEW_CATEGORIES: frozenset[str] = frozenset({"uncertain"})


def build_proposed_operation(
    *,
    file_id: str,
    original_relative_path: str,
    classification: ClassificationRecord,
) -> tuple[ProposedOperation | None, bool, str | None]:
    """Return a (ProposedOperation | None, needs_review, review_reason) tuple.

    Rules:
    - `uncertain` classifications always need review; no operation is proposed.
    - Any category without a known destination rule also triggers review.
    - All other categories receive a backend-generated destination using
      fixed folder rules. The filename is preserved; only the folder changes.
    """
    category = classification.category

    # A current document-aware record with an explicit null/non-transactional
    # kind must not become an expense operation merely because its safe folder
    # category is invoice or receipt. Legacy seven-field records retain the
    # category-based compatibility fallback inside this helper.
    if field_profile_for_classification(
        classification.model_dump(exclude_unset=True)
    ) != "transaction":
        return None, True, "Document is not a single transaction"

    if category in _REVIEW_CATEGORIES:
        return None, True, f"Category '{category}' requires human review"

    destination_folder = _CATEGORY_DESTINATION.get(category)
    if destination_folder is None:
        return None, True, f"No destination rule defined for category '{category}'"

    # Preserve only the filename; the backend owns the folder structure.
    filename = original_relative_path.rsplit("/", maxsplit=1)[-1]
    destination_relative_path = f"{destination_folder}/{filename}"

    # Build a human-readable reason from validated classification fields only.
    parts = [f"Classified as '{category}'"]
    if classification.merchant:
        parts.append(f"from {classification.merchant}")
    if classification.amount_text:
        parts.append(f"for {classification.amount_text}")
    reason = " ".join(parts) + "."

    operation = ProposedOperation(
        file_id=file_id,
        original_relative_path=original_relative_path,
        destination_relative_path=destination_relative_path,
        reason=reason,
    )
    return operation, False, None
