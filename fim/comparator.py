def compare_baseline(old_files: dict, new_files: dict) -> dict:
    """
    Compares old baseline files with newly scanned files.
    Returns a dict with created, deleted, modified.
    """

    created = []
    deleted = []
    modified = []

    # Check for deleted or modified
    for path, old_meta in old_files.items():
        if path not in new_files:
            deleted.append(path)
        else:
            new_meta = new_files[path]
            if old_meta["hash"] != new_meta["hash"]:
                modified.append(path)

    # Check for newly created files
    for path in new_files.keys():
        if path not in old_files:
            created.append(path)

    return {
        "created": created,
        "deleted": deleted,
        "modified": modified
    }
