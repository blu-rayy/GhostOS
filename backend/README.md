# GhostOS Backend

Phase 1 establishes the local FastAPI backend foundation. File scanning,
classification, file moving, undo, persistence, and AI integration are
intentionally deferred to later phases.

## Requirements

- Python 3.11 or newer

## Setup

From the `backend` directory, create and activate the virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell prevents activation, run this once for the current user or
session as appropriate:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Launch

With the virtual environment activated and the current directory set to
`backend`, start the development server:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server binds only to `127.0.0.1:8000`.

## Verify

Open <http://127.0.0.1:8000/> or run:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
```

The response should contain:

```json
{
  "app": "GhostOS",
  "status": "running",
  "phase": 1
}
```

FastAPI's interactive documentation is available at
<http://127.0.0.1:8000/docs>.

## Tests

From the `backend` directory, with the virtual environment activated, run:

```powershell
python -m pytest
```

The contract examples endpoint is available at
<http://127.0.0.1:8000/api/contracts/examples>.
