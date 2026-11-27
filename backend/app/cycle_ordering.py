"""Shared chronological ordering for academic-cycle records."""

import re
from typing import Iterable, TypeVar


CycleRecord = TypeVar("CycleRecord")


def _year(cycle: object) -> int:
    explicit = getattr(cycle, "academic_year", None)
    if explicit is not None:
        return int(explicit)
    text = " ".join(str(getattr(cycle, field, "") or "") for field in ("display_name", "name", "code"))
    matches = re.findall(r"\b(?:19|20|21)\d{2}\b", text)
    return int(matches[-1]) if matches else -1


def _session_rank(cycle: object) -> int:
    text = " ".join(str(getattr(cycle, field, "") or "") for field in ("session", "display_name", "name", "code")).upper()
    if "FALL" in text or "AUTUMN" in text:
        return 2
    if "SPRING" in text:
        return 1
    return 0


def _created_timestamp(cycle: object) -> float:
    value = getattr(cycle, "created_at", None)
    return value.timestamp() if value is not None and hasattr(value, "timestamp") else 0.0


def cycle_sort_key(cycle: object) -> tuple[int, int, float, int]:
    return (_year(cycle), _session_rank(cycle), _created_timestamp(cycle), int(getattr(cycle, "id", 0) or 0))


def sort_cycles_desc(cycles: Iterable[CycleRecord]) -> list[CycleRecord]:
    return sorted(cycles, key=cycle_sort_key, reverse=True)
