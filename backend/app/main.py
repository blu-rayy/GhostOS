"""Minimal FastAPI entry point for GhostOS Phase 1."""

from fastapi import FastAPI


app = FastAPI(title="GhostOS")


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
