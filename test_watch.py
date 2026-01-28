from pathlib import Path

from fim.watch import compare_file, normalize_event
from fim.utils import normalize_rel_path


def test_normalize_event_moved_becomes_delete_create():
    evs = normalize_event("moved", "C:/x/a.txt", "C:/x/b.txt")
    assert [e.kind for e in evs] == ["deleted", "created"]
    assert str(evs[0].abs_path).lower().endswith("a.txt")
    assert str(evs[1].abs_path).lower().endswith("b.txt")


def test_normalize_event_created_modified_deleted_passthrough():
    assert normalize_event("created", "C:/x/a.txt")[0].kind == "created"
    assert normalize_event("modified", "C:/x/a.txt")[0].kind == "modified"
    assert normalize_event("deleted", "C:/x/a.txt")[0].kind == "deleted"


def test_normalize_rel_path_windows_style_case_and_separators():
    # Works cross-platform: on Windows it lowercases, elsewhere it normalizes separators only.
    p = normalize_rel_path(r"Config\App.ini")
    assert "/" in p
    # should compare equal after normalization regardless of input case
    assert p == normalize_rel_path(r"config\app.ini")


def test_compare_file_created_when_not_in_baseline(tmp_path: Path):
    p = tmp_path / "new.txt"
    p.write_text("hello")
    res = compare_file(p, "new.txt", baseline_entry=None)
    assert res.change_type == "created"
    assert res.meta and isinstance(res.meta.get("hash"), str)
    assert res.unreadable is False


def test_compare_file_modified_when_hash_mismatch(tmp_path: Path):
    p = tmp_path / "file.txt"
    p.write_text("new content")
    baseline_entry = {"hash": "definitely-not-this"}
    res = compare_file(p, "file.txt", baseline_entry=baseline_entry)
    assert res.change_type == "modified"
    assert res.meta and res.meta["hash"] != baseline_entry["hash"]


def test_compare_file_deleted_when_missing_and_in_baseline(tmp_path: Path):
    p = tmp_path / "gone.txt"
    # intentionally do not create file
    baseline_entry = {"hash": "h1"}
    res = compare_file(p, "gone.txt", baseline_entry=baseline_entry)
    assert res.change_type == "deleted"
    assert res.meta is None


def test_compare_file_no_change_when_hash_matches(tmp_path: Path):
    p = tmp_path / "same.txt"
    p.write_text("same")
    # compute baseline hash by running compare_file once as created, then reuse it
    created = compare_file(p, "same.txt", baseline_entry=None)
    baseline_entry = {"hash": created.meta["hash"]}
    res = compare_file(p, "same.txt", baseline_entry=baseline_entry)
    assert res.change_type is None
    assert res.unreadable is False