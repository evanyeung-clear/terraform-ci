"""Utility helpers for Okta terraform import generation."""

import re
from typing import Iterable, Any


def sanitize_resource_name(name: str) -> str:
    """Sanitize a name to be used as a terraform resource name.

    Replaces non-alphanumeric characters with underscores, trims, lowers, and
    ensures the result neither starts with a number nor is empty.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    sanitized = sanitized.strip('_').lower()
    if sanitized and sanitized[0].isdigit():
        sanitized = f"resource_{sanitized}"
    if not sanitized:
        sanitized = "unnamed_resource"
    return sanitized


def sort_entities(items: Iterable[Any], key_attr: str):
    """Sort a collection of Okta model objects by a dynamic attribute path.

    key_attr may be a dotted path (e.g. 'profile.name'). Missing attrs are
    treated as empty strings to keep sort stable.
    """
    def resolve(obj, path: str):
        current = obj
        for part in path.split('.'):
            current = getattr(current, part, '')
        return (current or '').lower() if isinstance(current, str) else current

    return sorted(items, key=lambda o: resolve(o, key_attr))


def terraform_import_block(resource_type: str, resource_name: str, resource_id: str) -> str:
    """Generate a terraform import block string."""
    
    string = (f"import {{"
              f"  to = {resource_type}.{resource_name}"
              f"  id = \"{resource_id}\""
              f"}}")

    return string
