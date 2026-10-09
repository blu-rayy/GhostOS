from fastapi import APIRouter, HTTPException
from app.schemas import ClassifyRequest, ClassifyResponse
from app.services import local_ai
from app.services.document_awareness import document_kind_for_classification
from app.services.operations import build_proposed_operation

router = APIRouter(prefix="/api/classify", tags=["classify"])


@router.post("", response_model=ClassifyResponse)
def classify_file(request: ClassifyRequest) -> ClassifyResponse:
    """Classify one file's text excerpt using the local Ollama model.

    - Only accepts non-empty excerpts (validated by schema).
    - Sends the excerpt to Ollama at 127.0.0.1:11434.
    - Validates the response against the ClassificationRecord schema.
    - Generates a ProposedOperation using backend-only destination rules.
    - Marks uncertain or failed classifications as needing human review.
    - Does not access, move, or modify any files.
    """
    try:
        result = local_ai.classify_excerpt(request.text_excerpt)
    except local_ai.LocalAIInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except local_ai.LocalAIUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Local Ollama service is unavailable. Ensure it is running at 127.0.0.1:11434.",
        )
    except local_ai.LocalAITimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Local Ollama service timed out.",
        )
    except local_ai.LocalAIValidationError as exc:
        # Model returned a response that didn't match our schema.
        # Treat as uncertain — mark for human review rather than failing hard.
        from app.schemas import ClassificationRecord
        uncertain = ClassificationRecord(
            category="uncertain",
            explanation=f"Ollama response did not match the classification schema: {exc}",
        )
        return ClassifyResponse(
            file_id=request.file_id,
            classification=uncertain,
            proposed_operation=None,
            needs_review=True,
            review_reason="Model response failed schema validation",
            elapsed_seconds=0.0,
        )
    except local_ai.LocalAIResponseError as exc:
        raise HTTPException(status_code=502, detail=f"Unexpected response from Ollama: {exc}")

    classification = result.classification
    effective_kind = document_kind_for_classification(classification.model_dump())
    response_classification = classification.model_copy(update={"document_kind": effective_kind})

    # Backend generates the ProposedOperation — never Ollama.
    proposed_operation, needs_review, review_reason = build_proposed_operation(
        file_id=request.file_id,
        original_relative_path=request.file_id,  # frontend must supply this; placeholder safe here
        classification=classification,
    )

    return ClassifyResponse(
        file_id=request.file_id,
        classification=response_classification,
        field_profile=response_classification.field_profile,
        proposed_operation=proposed_operation,
        needs_review=needs_review,
        review_reason=review_reason,
        elapsed_seconds=result.elapsed_seconds,
    )
