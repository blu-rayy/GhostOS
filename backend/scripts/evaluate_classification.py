"""Interactive manual evaluation for the local GhostOS classifier.

Launch from the backend directory with:

    python scripts/evaluate_classification.py

Paste one document excerpt at a time, entering a line containing only ``END``
to finish that excerpt. Enter ``END`` immediately for an empty sample. The
script sends text only to the local Ollama adapter and does not read files or
write document contents to disk.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Make direct execution from the backend directory import the app package.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.classification_validation import (  # noqa: E402
    validate_classification,
)
from app.services.local_ai import (  # noqa: E402
    LocalAIError,
    classify_excerpt,
)


def _read_excerpt() -> str | None:
    """Read one multiline excerpt; return None when the session should end."""
    print("\nPaste document text. Enter END on its own line to finish.")
    lines: list[str] = []
    while True:
        line = input()
        if line == "END":
            return "\n".join(lines)
        lines.append(line)


def _display_result(excerpt: str) -> None:
    result = classify_excerpt(excerpt)
    classification = result.classification
    validation = validate_classification(excerpt, classification)

    print("\n--- Classification ---")
    print(f"Category: {classification.category}")
    print(f"Merchant: {classification.merchant}")
    print(f"Date: {classification.date}")
    print(f"Original amount_text: {classification.amount_text}")
    print(f"Currency: {classification.currency}")
    print(f"Evidence quote: {classification.evidence_quote}")
    print(f"Explanation: {classification.explanation}")

    print("\n--- Validation ---")
    print(f"is_valid: {validation.is_valid}")
    print(f"needs_review: {validation.needs_review}")
    print(f"Flags: {list(validation.flags)}")
    print(f"Parsed Decimal amount: {validation.parsed_amount}")
    print(f"Elapsed inference time: {result.elapsed_seconds:.3f} seconds")


def main() -> None:
    """Evaluate multiple manually pasted excerpts until interrupted or EOF."""
    print("GhostOS manual classification evaluation")
    print("This uses the real local Ollama classifier; no document files are read.")
    print("Press Ctrl+C or Ctrl+D to exit.")

    while True:
        try:
            excerpt = _read_excerpt()
        except (KeyboardInterrupt, EOFError):
            print("\nEvaluation session ended.")
            return

        if excerpt is None:
            print("Evaluation session ended.")
            return
        if not excerpt.strip():
            print("Empty input skipped. Enter another excerpt or END to exit.")
            continue

        try:
            _display_result(excerpt)
        except (LocalAIError, TypeError, ValueError) as exc:
            print(f"Evaluation error: {type(exc).__name__}: {exc}")
            print("The session remains active; enter another excerpt or END.")
        except KeyboardInterrupt:
            print("\nEvaluation session ended.")
            return


if __name__ == "__main__":
    main()
