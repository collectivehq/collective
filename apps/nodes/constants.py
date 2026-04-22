from __future__ import annotations

# Mirrors Node.ResolutionType choices — update in sync with that enum.
VALID_RESOLUTION_TYPES: frozenset[str] = frozenset({"accept", "reject", "close"})
