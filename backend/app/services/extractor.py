import hashlib
import fitz  # PyMuPDF
from pathlib import Path
from typing import Tuple, Optional

# Max characters to extract to keep payload sizes reasonable
MAX_EXCERPT_LENGTH = 1500

def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_text_from_pdf(filepath: Path) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    text = ""
    try:
        with fitz.open(filepath) as doc:
            for page in doc:
                text += page.get_text()
                if len(text) > MAX_EXCERPT_LENGTH:
                    break
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {str(e)}")
    return text.strip()

def extract_text_from_plain(filepath: Path) -> str:
    """Extract text from a plain text or CSV file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(MAX_EXCERPT_LENGTH + 100)
    except Exception as e:
        raise RuntimeError(f"Text extraction failed: {str(e)}")
    return text.strip()

def process_file_content(filepath: Path, extension: str) -> Tuple[Optional[str], str, str, Optional[str]]:
    """
    Process the file to get SHA-256 and extracted text excerpt.
    Returns:
        Tuple of (sha256_hash, extraction_status, text_excerpt, reason)
    """
    try:
        sha256_hash = compute_sha256(filepath)
    except Exception as e:
        return None, "error", "", f"Hashing failed: {str(e)}"
        
    text = ""
    status = "skipped"
    reason = None
    
    try:
        if extension in {".txt", ".csv"}:
            text = extract_text_from_plain(filepath)
            status = "success"
        elif extension == ".pdf":
            text = extract_text_from_pdf(filepath)
            status = "success"
        else:
            status = "skipped"
            reason = "Unsupported extension for extraction"
            
        if status == "success" and not text:
            status = "empty"
            reason = "No text content found in file"
            
    except Exception as e:
        status = "error"
        reason = str(e)
        
    # Bound the excerpt length
    excerpt = text[:MAX_EXCERPT_LENGTH]
    
    return sha256_hash, status, excerpt, reason
