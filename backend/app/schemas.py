from pydantic import BaseModel
from typing import List, Optional

class ScanRequest(BaseModel):
    root_path: str

class FileRecord(BaseModel):
    file_id: str
    relative_path: str
    filename: str
    extension: str
    size_bytes: int
    sha256: Optional[str] = None
    extraction_status: str = "skipped"
    text_excerpt: str = ""
    reason: str = "Pending text extraction and hashing"

class ScanResponse(BaseModel):
    root_path: str
    total_files: int
    files: List[FileRecord]
