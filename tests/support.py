"""Shared fixtures for unit tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from worklog.config import Source
from worklog.extract import Context
from worklog.model import window_bounds
from worklog.redact import compile_excludes

UTC = timezone.utc
NOW = datetime(2026, 10, 15, 21, 0, tzinfo=UTC)


def context(now=NOW, days=14, patterns=None, names=None, home=None, seen=None):
    start, _end = window_bounds(now, days)
    ctx = Context(
        now=now,
        days=days,
        window_start=start,
        exclude_res=compile_excludes(list(patterns or [])),
        project_names=dict(names or {}),
        home=home or Path("/home/does-not-exist"),
    )
    if seen:
        ctx.seen.update(seen)
    return ctx


def source(kind, paths, source_id="src", label=None, explicit=True):
    return Source(
        id=source_id,
        label=label or source_id,
        kind=kind,
        paths=[Path(p) for p in paths],
        enabled=True,
        explicit_paths=explicit,
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
