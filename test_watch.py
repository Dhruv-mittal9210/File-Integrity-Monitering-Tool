from fim.watch import classify_change


def test_classify_change_created():
    baseline = {"a.txt": {"hash": "old"}}
    new_meta = {"hash": "new"}
    assert classify_change("new.txt", baseline, new_meta) == "created"


def test_classify_change_modified():
    baseline = {"file.txt": {"hash": "old"}}
    new_meta = {"hash": "new"}
    assert classify_change("file.txt", baseline, new_meta) == "modified"


def test_classify_change_deleted():
    baseline = {"gone.txt": {"hash": "h1"}}
    assert classify_change("gone.txt", baseline, None) == "deleted"


def test_classify_change_noop_same_hash():
    baseline = {"same.txt": {"hash": "abc"}}
    new_meta = {"hash": "abc"}
    assert classify_change("same.txt", baseline, new_meta) is None