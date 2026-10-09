"""MOCK BACKEND for the DA-5 retest (Developer 4 / QA).

Runs the UNMODIFIED production FastAPI app on 127.0.0.1:8001 with ONE substitution:
`app.services.local_ai.classify_excerpt` returns fixed, deterministic classifications
chosen by a marker in the excerpt. No Ollama call is made. Everything else (routes,
orchestrator, validator, plan builder, approve/undo, report writer) is production code.

Results from this server are MOCKED-classifier results, not live-model behaviour.

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\document_aware_review\\da5_retest_3c60bb3\\scripts\\mock_backend.py
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "backend"))

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import ClassificationRecord  # noqa: E402
from app.services import local_ai  # noqa: E402

# marker in excerpt -> model JSON payload. A payload WITHOUT "document_kind" models a response
# that omits the field; a payload with "document_kind": None models an explicit null.
# Order matters: the card statement's text also contains "SUNBEAM CAFE" (one of its listed charges),
# so the statement markers are checked first. (The first run used the opposite order: invalid B2 result.)
MOCK_RESPONSES = [
    ("HARBOR FEDERAL BANK", {"category": "invoice", "merchant": "HARBOR FEDERAL BANK", "date": "2026-09-25",
                             "amount_text": "PHP 5,391.06", "currency": "PHP",
                             "evidence_quote": "Statement balance: PHP 5,391.06", "explanation": "MOCK: kind omitted"}),
    ("SUNBEAM CAFE", {"category": "receipt", "document_kind": "receipt", "merchant": "SUNBEAM CAFE", "date": "2026-09-21",
                      "amount_text": "PHP 683.20", "currency": "PHP", "evidence_quote": "FINAL TOTAL: PHP 683.20",
                      "explanation": "MOCK: valid receipt"}),
    ("Tibay Hardware", {"category": "receipt", "document_kind": "receipt", "merchant": "Tibay Hardware", "date": "2026-09-27",
                        "amount_text": "2145.00", "currency": "PHP", "evidence_quote": "grand_total,,,2145.00",
                        "explanation": "MOCK: valid receipt"}),
    ("SAMPLE NATIONAL BANK", {"category": "invoice", "document_kind": None, "merchant": "SAMPLE NATIONAL BANK",
                              "date": "2026-09-30", "amount_text": "PHP 9,120.50", "currency": "PHP",
                              "evidence_quote": "Closing balance: PHP 9,120.50", "explanation": "MOCK: explicit null kind"}),
    ("MOCK-STATEMENT", {"category": "invoice", "document_kind": "statement", "merchant": None, "date": None,
                        "amount_text": None, "currency": None, "evidence_quote": "MOCK-STATEMENT", "explanation": "MOCK: statement"}),
    ("MOCK-IDENTITY", {"category": "invoice", "document_kind": "identity_or_civil", "merchant": None, "date": None,
                       "amount_text": None, "currency": None, "evidence_quote": "MOCK-IDENTITY", "explanation": "MOCK: identity"}),
    ("MOCK-NULLKIND", {"category": "invoice", "document_kind": None, "merchant": "X", "date": "2026-09-01",
                       "amount_text": "PHP 100.00", "currency": "PHP", "evidence_quote": "MOCK-NULLKIND PHP 100.00",
                       "explanation": "MOCK: explicit null"}),
    ("MOCK-OMITKIND", {"category": "invoice", "merchant": "X", "date": "2026-09-01", "amount_text": "PHP 100.00",
                       "currency": "PHP", "evidence_quote": "MOCK-OMITKIND PHP 100.00", "explanation": "MOCK: kind omitted"}),
]


def mock_classify_excerpt(excerpt, **_kwargs):
    for marker, payload in MOCK_RESPONSES:
        if marker in excerpt:
            return local_ai.ClassificationResult(classification=ClassificationRecord.model_validate(payload), elapsed_seconds=0.0)
    raise local_ai.LocalAIResponseError("MOCK: no fixed response for this excerpt")


local_ai.classify_excerpt = mock_classify_excerpt

if __name__ == "__main__":
    print("MOCK BACKEND: production app, mocked classifier, 127.0.0.1:8001", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8001)
