"""Shared records and time helpers. Python 3.9 compatible."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

FILES_SHOWN = 25
FILES_DISPLAY = 6

_FRACTION = re.compile(r"\.(\d+)(?=(?:[+-]\d{2}:\d{2})|Z|$)")


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp. A trailing Z is accepted on Python 3.9."""
    text = str(value).strip()
    if not text:
        raise ValueError("empty timestamp")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # 3.9 accepts isoformat output, including fractional seconds and offsets.
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        stripped = _FRACTION.sub("", text)
        return datetime.fromisoformat(stripped)


def aware(dt: datetime, now: datetime) -> datetime:
    """Attach `now`'s zone to a naive timestamp, or convert an aware one."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=now.tzinfo)
    return dt.astimezone(now.tzinfo)


def window_bounds(now: datetime, days: int) -> tuple[datetime, datetime]:
    """Inclusive local calendar window ending today, `days` dates long."""
    if days < 1:
        raise ValueError("days must be at least 1")
    local_now = aware(now, now)
    today = local_now.date()
    start_day = today - timedelta(days=days - 1)
    start = datetime(start_day.year, start_day.month, start_day.day, tzinfo=local_now.tzinfo)
    return start, local_now


def in_window(dt: datetime, now: datetime, days: int) -> bool:
    start, local_now = window_bounds(now, days)
    local = aware(dt, now)
    return start.date() <= local.date() <= local_now.date()


def short_path(path: str | None, cwd: str | None, home: Path) -> str:
    """Prefer a cwd-relative path, then a ~/ path. Never raises."""
    if not path:
        return ""
    try:
        pp = Path(path)
    except (TypeError, ValueError):
        return str(path)
    try:
        if cwd:
            base = Path(cwd)
            prefix = str(base).rstrip("/")
            full = str(pp)
            if full == prefix:
                return "."
            if full.startswith(prefix + "/"):
                return str(pp.relative_to(base))
        home_prefix = str(home).rstrip("/")
        if str(pp).startswith(home_prefix + "/"):
            return "~/" + str(pp.relative_to(home))
    except (ValueError, OSError):
        pass
    return str(path)


def project_name(cwd: str | None, home: Path, fallback: str) -> str:
    if not cwd:
        return fallback or "(unknown)"
    try:
        path = Path(cwd)
    except (TypeError, ValueError):
        return fallback or "(unknown)"
    if str(path).rstrip("/") == str(home).rstrip("/"):
        return "~ (home)"
    name = path.name
    return name or fallback or "(unknown)"


def display_project(name: str, mapping: dict[str, str]) -> str:
    return mapping.get(name, name)


def iso_seconds(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds")


def make_entry(
    *,
    source: str,
    project: str,
    title: str,
    start: datetime,
    end: datetime,
    status: str = "",
    agent: str = "",
    links: list[dict] | None = None,
    files: list[str] | None = None,
    files_total: int | None = None,
    session_id: str = "",
    detail: str = "",
    cwd: str = "",
) -> dict:
    found = list(files or [])
    total = len(found) if files_total is None else int(files_total)
    return {
        "source": source,
        "project": project,
        "title": title or "(untitled)",
        "start": iso_seconds(start),
        "end": iso_seconds(end),
        "status": status or "",
        "agent": agent or "",
        "links": list(links or []),
        "files": found[:FILES_SHOWN],
        "files_total": total,
        "session_id": session_id or "",
        "detail": detail or "",
        "cwd": cwd or "",
    }


# Re-export for callers that only need a UTC constant.
UTC = timezone.utc
