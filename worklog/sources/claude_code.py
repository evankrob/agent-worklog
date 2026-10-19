"""Claude Code session adapter.

Reads ``<config-dir>/projects/*/*.jsonl`` (one file per top-level session).
Deeper files are sub-agent transcripts and are ignored. For each session the
adapter keeps a redacted title (100 characters), the project, the time span,
and the paths of files written or edited. Message bodies and tool arguments
other than the path are discarded.
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
    parse_iso,
    project_name,
    short_path,
)
from worklog.redact import is_excluded, redact, title_from

WRITE_TOOLS = {
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "create_file",
    "str_replace",
    "str_replace_based_edit_tool",
}

EXCLUDED = object()


def extract_claude_code(source, ctx) -> tuple[list[dict], int, list[str]]:
    entries: list[dict] = []
    excluded = 0
    warnings: list[str] = []
    for directory in source.paths:
        projects = directory / "projects"
        if not projects.is_dir():
            warnings.append("%s: no Claude Code projects at %s" % (source.id, directory))
            continue
        detail = _instance_label(directory, len(source.paths))
        for path in sorted(projects.glob("*/*.jsonl")):
            try:
                if path.stat().st_mtime < ctx.window_start.timestamp():
                    continue
            except OSError as exc:
                warnings.append("%s: skipped %s (%s)" % (source.id, path.name, type(exc).__name__))
                continue
            try:
                result = scan_session(path, source.id, detail, ctx)
            except Exception as exc:  # noqa: BLE001 — one bad file should not stop the log
                warnings.append("%s: skipped %s (%s)" % (source.id, path.name, type(exc).__name__))
                print("skip %s %s" % (path.name, type(exc).__name__), file=sys.stderr)
                continue
            if result is EXCLUDED:
                excluded += 1
            elif result:
                entries.append(result)
    return entries, excluded, warnings


def collect_session_ids(directory: Path) -> set[str]:
    projects = directory / "projects"
    if not projects.is_dir():
        return set()
    return {path.stem for path in projects.glob("*/*.jsonl")}


def scan_session(path: Path, source_id: str, detail: str, ctx):
    """Stream one JSONL session. Returns an entry, EXCLUDED, or None."""
    start = end = None
    cwd = None
    first = None
    custom = None
    files: list[str] = []
    meta_excluded = False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            stamp = _stamp(record.get("timestamp"))
            if stamp is not None:
                start = stamp if start is None or stamp < start else start
                end = stamp if end is None or stamp > end else end
            if not cwd and isinstance(record.get("cwd"), str):
                cwd = record["cwd"]
            if record.get("type") == "custom-title" and isinstance(record.get("customTitle"), str):
                custom = record["customTitle"]
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            if (
                record.get("type") == "user"
                and first is None
                and not record.get("isSidechain")
                and not record.get("isMeta")
                and not record.get("toolUseResult")
            ):
                text = _text_of(message.get("content"))[:20000]
                candidate = title_from(text) if text else ""
                if candidate and not candidate.startswith("Caveat:"):
                    first = text
            if record.get("type") == "assistant" and isinstance(message.get("content"), list):
                for block in message["content"]:
                    path_written = _written_path(block)
                    if not path_written:
                        continue
                    if is_excluded(ctx.exclude_res, [path_written]):
                        meta_excluded = True
                    short = redact(short_path(path_written, cwd, ctx.home))
                    if short and short not in files:
                        files.append(short)
    if start is None or end is None:
        return None
    if not in_window(end, ctx.now, ctx.days):
        return None
    blobs = [cwd or "", first or "", custom or "", path.parent.name]
    if meta_excluded or is_excluded(ctx.exclude_res, blobs):
        return EXCLUDED
    fallback = path.parent.name
    raw_project = project_name(cwd, ctx.home, fallback)
    project = redact(display_project(raw_project, ctx.project_names)) or "(unknown)"
    if custom:
        title = title_from(custom)
    elif first:
        title = title_from(first)
    else:
        title = "(no prompt)"
    if not title:
        title = "(no prompt)"
    shown_cwd = redact(short_path(cwd, None, ctx.home)) if cwd else ""
    return make_entry(
        source=source_id,
        project=project,
        title=title,
        start=start,
        end=end,
        files=files,
        files_total=len(files),
        session_id=path.stem,
        detail=detail,
        cwd=shown_cwd,
    )


def _written_path(block: object) -> str:
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return ""
    if block.get("name") not in WRITE_TOOLS:
        return ""
    payload = block.get("input")
    if not isinstance(payload, dict):
        return ""
    # Only the path is read. File contents and patches are never copied.
    for key in ("file_path", "notebook_path", "path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return " ".join(parts)
    return ""


def _stamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return parse_iso(value)
    except ValueError:
        return None


def _instance_label(directory: Path, count: int) -> str:
    """A short column note when several Claude config dirs share one source."""
    if count < 2:
        return ""
    name = directory.name[1:] if directory.name.startswith(".") else directory.name
    if name == "claude":
        return ""
    if name.startswith("claude-"):
        return name[len("claude-") :]
    return name
