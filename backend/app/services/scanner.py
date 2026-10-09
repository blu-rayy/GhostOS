import os
import hashlib
from pathlib import Path
from typing import List
from app.schemas import FileRecord

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv"}
MAX_FILES = 100
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def generate_file_id(relative_path: str) -> str:
    return hashlib.md5(relative_path.encode('utf-8')).hexdigest()[:8]

def scan_folder(root_path_str: str) -> List[FileRecord]:
    root_path = Path(root_path_str)
    
    if root_path.is_symlink():
        raise ValueError("Symlinked roots are not allowed")
        
    try:
        resolved_root = root_path.resolve(strict=True)
    except Exception:
        raise ValueError("Invalid or inaccessible root folder")
        
    if not resolved_root.is_dir():
        raise ValueError("Root path must be a directory")

    records: List[FileRecord] = []
    
    for root_dir, dirs, files in os.walk(resolved_root, followlinks=False):
        if len(records) >= MAX_FILES:
            break
            
        for file in files:
            if len(records) >= MAX_FILES:
                break
                
            ext = os.path.splitext(file)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
                
            file_path = Path(root_dir) / file
            
            if file_path.is_symlink():
                continue
                
            try:
                stat = file_path.stat()
                if stat.st_size > MAX_FILE_SIZE:
                    continue
                    
                resolved_file = file_path.resolve(strict=True)
                if resolved_root not in resolved_file.parents:
                     continue
                     
                rel_path = file_path.relative_to(resolved_root).as_posix()
                
                records.append(FileRecord(
                    file_id=generate_file_id(rel_path),
                    relative_path=rel_path,
                    filename=file,
                    extension=ext,
                    size_bytes=stat.st_size,
                    extraction_status="skipped",
                    reason="Pending text extraction and hashing",
                ))
            except Exception:
                # Handle inaccessible files gracefully
                continue
                
    return records
