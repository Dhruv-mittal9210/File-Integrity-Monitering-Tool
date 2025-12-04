# tests/test_comparator.py
from fim.comparator import compare_baseline

def test_compare_baseline_added_modified_deleted():
    old = {
        "a.txt": {"hash": "h1"},
        "b.txt": {"hash": "h2"},
        "c.txt": {"hash": "h3"}
    }

    new = {
        "a.txt": {"hash": "h1"},        # same
        "b.txt": {"hash": "h2_mod"},    # modified
        "d.txt": {"hash": "h4"}         # new
        # c.txt deleted
    }

    changes = compare_baseline(old, new)
    assert set(changes["created"]) == {"d.txt"}
    assert set(changes["modified"]) == {"b.txt"}
    assert set(changes["deleted"]) == {"c.txt"}
