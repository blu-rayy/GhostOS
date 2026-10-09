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

## API Endpoints

### `POST /api/scan`

Scans a selected local folder and returns a structured metadata inventory for supported files (PDF, TXT, CSV).

**Request Body:**

```json
{
  "root_path": "C:\\Users\\YourName\\Documents\\GhostOSTest"
}
```

**Response Example:**

```json
{
  "root_path": "C:\\Users\\YourName\\Documents\\GhostOSTest",
  "total_files": 1,
  "files": [
    {
      "file_id": "a1b2c3d4",
      "relative_path": "receipts/coffee.pdf",
      "filename": "coffee.pdf",
      "extension": ".pdf",
      "size_bytes": 10240,
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "extraction_status": "success",
      "text_excerpt": "COFFEE SHOP RECEIPT\nTotal: $4.50",
      "reason": null
    }
  ]
}
```

**Features & Safety:**
- Recursively discovers supported files inside the folder.
- Rejects invalid or symlinked roots.
- Limits scanning to 100 files and skips files larger than 10 MB.
- Does not modify, move, or rename source files.

## Tests

From the `backend` directory, with the virtual environment activated, run:

```powershell
python -m pytest
```

The contract examples endpoint is available at
<http://127.0.0.1:8000/api/contracts/examples>.
