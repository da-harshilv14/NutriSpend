def normalize_name(name: str) -> str:
    """Canonical lookup key: lowercased, whitespace-collapsed.

    Used at BOTH seed time and query time so exact match stays consistent.
    """
    return " ".join(str(name).lower().split())
