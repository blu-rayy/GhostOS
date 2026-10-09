import pytest
from pathlib import Path
from app.services.extractor import process_file_content, compute_sha256

def test_extract_text_from_plain(tmp_path):
    text_file = tmp_path / "test.txt"
    content = "Hello GhostOS"
    text_file.write_text(content)
    
    sha256, status, excerpt, reason = process_file_content(text_file, ".txt")
    assert status == "success"
    assert excerpt == content
    assert sha256 == compute_sha256(text_file)
    assert reason is None

def test_extract_text_empty_plain(tmp_path):
    text_file = tmp_path / "empty.txt"
    text_file.write_text("")
    
    sha256, status, excerpt, reason = process_file_content(text_file, ".txt")
    assert status == "empty"
    assert excerpt == ""
    assert reason == "No text content found in file"

def test_extract_invalid_pdf(tmp_path):
    pdf_file = tmp_path / "bad.pdf"
    pdf_file.write_bytes(b"not a valid pdf file")
    
    sha256, status, excerpt, reason = process_file_content(pdf_file, ".pdf")
    assert status == "error"
    assert "PDF extraction failed" in reason

def test_extract_unsupported(tmp_path):
    img_file = tmp_path / "img.png"
    img_file.write_bytes(b"image data")
    
    sha256, status, excerpt, reason = process_file_content(img_file, ".png")
    assert status == "skipped"
    assert "Unsupported extension" in reason
    assert excerpt == ""
