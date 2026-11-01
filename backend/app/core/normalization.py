"""Small shared normalization helpers."""

import re

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def organization_slug(name: str) -> str:
    """Create a readable URL-safe organization slug base."""
    slug = _SLUG_PATTERN.sub("-", name.lower()).strip("-")[:160]
    return slug or "organization"
