"""Pure validation functions: no Home Assistant imports."""

from __future__ import annotations

from typing import Any

PROFILES = frozenset(("full", "partial"))


def parse_slot(value: Any) -> int | None:
    """Accept only a decimal slot ID from 1 to 199, never bools/floats."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        slot = value
    elif isinstance(value, str) and value.strip().isascii() and value.strip().isdecimal():
        slot = int(value.strip())
    else:
        return None
    return slot if 1 <= slot <= 199 else None


def validate_person(name: str, profile: str) -> dict[str, str]:
    """Return a normalized person, refusing unrecognized privileges."""
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise ValueError("Name must be between 1 and 80 characters")
    if profile not in PROFILES:
        raise ValueError("Unknown access profile")
    return {"name": name.strip(), "profile": profile}


def lookup_person(people: dict[str, dict[str, str]], slot: Any) -> dict[str, str] | None:
    """Fail closed on malformed or unknown IDs and profiles."""
    valid = parse_slot(slot)
    if valid is None:
        return None
    person = people.get(str(valid))
    if not isinstance(person, dict):
        return None
    if person.get("profile") not in PROFILES:
        return None
    if not isinstance(person.get("name"), str) or not person["name"].strip():
        return None
    return person
