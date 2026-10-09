import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def temp_dir(tmp_path):
    test_dir = tmp_path / "test_scan"
    test_dir.mkdir()
    
    (test_dir / "doc1.pdf").write_bytes(b"dummy pdf")
    (test_dir / "doc2.txt").write_bytes(b"dummy txt")
    (test_dir / "data.csv").write_bytes(b"dummy csv")
    
    sub = test_dir / "sub"
    sub.mkdir()
    (sub / "doc3.pdf").write_bytes(b"sub pdf")
    
    (test_dir / "image.png").write_bytes(b"image")
    
    large = test_dir / "large.txt"
    with large.open("wb") as f:
        f.seek((10 * 1024 * 1024) + 1)
        f.write(b"0")
        
    yield test_dir
    
def test_scan_endpoint_valid(temp_dir):
    response = client.post("/api/scan", json={"root_path": str(temp_dir)})
    assert response.status_code == 200
    data = response.json()
    assert data["root_path"] == str(temp_dir)
    assert data["total_files"] == 4
    filenames = [f["filename"] for f in data["files"]]
    assert "doc1.pdf" in filenames
    assert "doc2.txt" in filenames
    assert "data.csv" in filenames
    assert "doc3.pdf" in filenames
    assert "image.png" not in filenames
    assert "large.txt" not in filenames

def test_scan_endpoint_invalid_path():
    response = client.post("/api/scan", json={"root_path": "/invalid/nonexistent/path"})
    assert response.status_code == 400
    assert "Invalid or inaccessible root folder" in response.json()["detail"]
