"""Minimal FastAPI entry point for GhostOS Phase 1."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import scan
from app.routes import classify
from app.routes import session

from app.routes.contracts import router as contracts_router


app = FastAPI(title="GhostOS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

app.include_router(contracts_router)

app.include_router(scan.router)
app.include_router(classify.router)
app.include_router(session.router)


@app.get("/")
def read_root() -> dict[str, str | int]:
    """Return the backend health/status payload."""
    return {
        "app": "GhostOS",
        "status": "running",
        "phase": 1,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
