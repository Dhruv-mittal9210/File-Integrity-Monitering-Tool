# tests/test_scanner.py
from pathlib import Path
from fim.scanner import scan_directory

def test_scan_collects_metadata(tmp_path: Path):
    d = tmp_path / "dir"
    d.mkdir()
    f1 = d / "one.txt"
    f1.write_text("a")
    f2 = d / "sub.py"
    f2.write_text("b")
    res = scan_directory(d, exclude=[])
    assert "one.txt" in res
    assert "sub.py" in res
    assert "one.txt" in res and "hash" in res["one.txt"]

def test_scan_exclude_glob(tmp_path: Path):
    d = tmp_path / "dir2"
    d.mkdir()
    (d / "a.pyc").write_text("x")
    (d / "b.txt").write_text("y")
    res = scan_directory(d, exclude=["*.pyc"])
    assert "b.txt" in res
    assert "a.pyc" not in res
