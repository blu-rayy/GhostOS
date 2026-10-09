from fastapi import APIRouter, HTTPException
from app.schemas import ScanRequest, ScanResponse
from app.services.scanner import scan_folder

router = APIRouter(prefix="/api/scan", tags=["scan"])

@router.post("", response_model=ScanResponse)
def scan_directory(request: ScanRequest):
    try:
        files = scan_folder(request.root_path)
        return ScanResponse(
            root_path=request.root_path,
            total_files=len(files),
            files=files
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
