"""Stable automatic names for cycle-scoped student groups."""

from __future__ import annotations

import re

from .models import AcademicCycle


def cycle_period(cycle: AcademicCycle) -> str | None:
    year = cycle.academic_year
    session = (cycle.session or "").strip().upper()
    source = " ".join(value for value in (cycle.display_name, cycle.code) if value)
    if year is None:
        year_match = re.search(r"\b(19|20)\d{2}\b", source)
        year = int(year_match.group(0)) if year_match else None
    if session not in {"FALL", "SPRING"}:
        session_match = re.search(r"\b(FALL|SPRING)\b", source.upper())
        session = session_match.group(1) if session_match else ""
    if year is None or not session:
        return None
    return f"{session.title()} {year}"


def generated_group_name(cycle: AcademicCycle, group_number: int | None) -> str:
    period = cycle_period(cycle)
    number = group_number if group_number is not None else "—"
    return f"{period} Group {number}" if period else f"Group {number}"
