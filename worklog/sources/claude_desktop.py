"""Claude desktop adapter (macOS).

Reads the small session metadata under Claude's Application Support folder
(title, folders, timestamps). When a cowork session has a transcript next to
that metadata, the transcript is streamed only to collect written file paths.
The initial message and transcript bodies are not stored.

On other operating systems the adapter does nothing unless you pass an
explicit path (used for tests and for a copied metadata folder).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from worklog.model import (
    display_project,
    in_window,
    make_entry,
    project_name,
    short_path,
)
from worklog.redact import is_excluded, redact, title_from
from worklog.sources.claude_code import EXCLUDED, scan_session

_KINDS = ("local-agent-mode-sessions", "claude-code-sessions")
_MAX_META_BYTES = 2_000_000


def extract_desktop(source, ctx) -> tuple[list[dict], int, list[str]]:
    entries: list[dict] = []
    excluded = 0
    warnings: list[str] = []
    # The default folder only exists on macOS. An explicit path (a fixture, or a
    # copied metadata directory) is read on any system.
    if not getattr(source, "explicit_paths", False) and sys.platform != "darwin":
        warnings.append(
            "%s: Claude desktop is optional and only reads its data on macOS" % source.id
        )
        return entries, excluded, warnings
    for root in source.paths:
        if not root.is_dir():
            warnings.append("%s: Claude desktop data not found at %s" % (source.id, root))
            continue
        found, skipped, warns = _scan_root(root, source, ctx)
        entries.extend(found)
        excluded += skipped
        warnings.extend(warns)
    return entries, excluded, warnings


def _scan_root(root: Path, source, ctx) -> tuple[list[dict], int, list[str]]:
    entries: list[dict] = []
    excluded = 0
    warnings: list[str] = []
    for kind in _KINDS:
        base = root / kind
        if not base.is_dir():
            continue
        for meta in sorted(base.glob("*/*/local_*.json")):
            try:
                if meta.stat().st_size > _MAX_META_BYTES:
                    warnings.append("%s: skipped large metadata %s" % (source.id, meta.name))
                    continue
                if meta.stat().st_mtime < ctx.window_start.timestamp():
                    continue
                record = json.loads(meta.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError) as exc:
                warnings.append("%s: skipped %s (%s)" % (source.id, meta.name, type(exc).__name__))
                continue
            if not isinstance(record, dict):
                continue
            built, was_excluded = _one(meta, record, kind, source, ctx)
            if was_excluded:
                excluded += 1
            elif built:
                entries.append(built)
    return entries, excluded, warnings


def _one(meta: Path, record: dict, kind: str, source, ctx):
    last_ms = record.get("lastActivityAt") or 0
    try:
        last_ms = float(last_ms)
    except (TypeError, ValueError):
        return None, False
    if last_ms <= 0:
        return None, False
    end = datetime.fromtimestamp(last_ms / 1000.0).astimezone(ctx.now.tzinfo)
    if not in_window(end, ctx.now, ctx.days):
        return None, False
    cli = record.get("cliSessionId") or ""
    if isinstance(cli, str) and cli and cli in ctx.seen:
        return None, False
    selected = record.get("userSelectedFolders") or []
    if not isinstance(selected, list):
        selected = []
    cwd = record.get("originCwd") or record.get("cwd") or ""
    if not isinstance(cwd, str):
        cwd = ""
    folder = ""
    if kind.startswith("local") and selected and isinstance(selected[0], str):
        folder = selected[0]
    else:
        folder = cwd
    title = record.get("title") if isinstance(record.get("title"), str) else ""
    initial = record.get("initialMessage") if isinstance(record.get("initialMessage"), str) else ""
    blob_parts = [folder, cwd, title] + [str(item) for item in selected]
    if is_excluded(ctx.exclude_res, [" ".join(blob_parts), initial[:5000]]):
        return None, True
    files: list[str] = []
    if kind.startswith("local") and isinstance(cli, str) and cli:
        transcript_root = meta.parent / meta.stem
        for transcript in transcript_root.glob(".claude/projects/*/%s.jsonl" % cli):
            try:
                scanned = scan_session(transcript, source.id, "", ctx)
            except OSError:
                continue
            if scanned is EXCLUDED:
                return None, True
            if isinstance(scanned, dict):
                for item in scanned.get("files") or []:
                    if item not in files:
                        files.append(item)
    useful = [item for item in files if not str(item).startswith("/sessions/")]
    files = useful or files
    raw_project = project_name(
        folder,
        ctx.home,
        "Cowork" if kind.startswith("local") else "Claude Code (desktop)",
    )
    project = redact(display_project(raw_project, ctx.project_names)) or "(unknown)"
    created = record.get("createdAt") or record.get("lastActivityAt")
    try:
        start = datetime.fromtimestamp(float(created) / 1000.0).astimezone(ctx.now.tzinfo)
    except (TypeError, ValueError):
        start = end
    if isinstance(cli, str) and cli:
        ctx.seen.add(cli)
    detail = "cowork" if kind.startswith("local") else "code tab"
    return (
        make_entry(
            source=source.id,
            project=project,
            title=title_from(title) if title else "(untitled)",
            start=start,
            end=end,
            files=files,
            files_total=len(files),
            session_id=(cli if isinstance(cli, str) and cli else meta.stem),
            detail=detail,
            cwd=redact(short_path(folder, None, ctx.home)) if folder else "",
        ),
        False,
    )
