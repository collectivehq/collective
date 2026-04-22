from __future__ import annotations

# Mirrors Discussion.ResolutionType choices — keep in sync with the model enum.
VALID_RESOLUTION_TYPES: frozenset[str] = frozenset({"accept", "reject", "close"})
