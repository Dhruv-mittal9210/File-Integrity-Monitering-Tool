from pathlib import Path
from fim.hasher import hash_file

def test_hash_file_simple(tmp_path: Path):
    p = tmp_path / "a.txt"
    p.write_text("hello")
    h = hash_file(p)
    assert isinstance(h, str) and len(h) == 64

def test_hash_file_unreadable(tmp_path: Path):
    p = tmp_path / "locked.txt"
    p.write_text("secret")
    # simulate unreadable by opening with exclusive on some platforms; fallback: remove file
    # We'll delete then call hash_file which should return None gracefully
    p.unlink()
    h = hash_file(p)
    assert h is None