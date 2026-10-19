"""Generic JSON / JSONL adapter.

Any agent can append one object per line (or a JSON array) and show up as
its own column. Only the summary fields below are kept; unknown fields are
ignored so a verbose log cannot leak into the page.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from worklog.model import aware, display_project, in_window, make_entry, parse_iso
from worklog.redact import is_excluded, redact, title_from

_CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?\s*$")
_DATE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")


def extract_json(source, ctx) -> tuple[list[dict], int, list[str]]:
    entries: list[dict] = []
    excluded = 0
    warnings: list[str] = []
    if not source.paths:
        warnings.append("%s: no path configured" % source.id)
        return entries, excluded, warnings
    for path in source.paths:
        if path.is_dir():
            files = sorted(path.glob("*.json")) + sorted(path.glob("*.jsonl")) + sorted(path.glob("*/*.jsonl"))
            if not files:
                warnings.append("%s: no JSON logs in %s" % (source.id, path))
            for child in files:
                got, skipped, warns = _read_file(child, source, ctx)
                entries.extend(got)
                excluded += skipped
                warnings.extend(warns)
            continue
        if not path.is_file():
            warnings.append("%s: log not found: %s" % (source.id, path))
            continue
        got, skipped, warns = _read_file(path, source, ctx)
        entries.extend(got)
        excluded += skipped
        warnings.extend(warns)
    return entries, excluded, warnings


def _read_file(path, source, ctx) -> tuple[list[dict], int, list[str]]:
    entries: list[dict] = []
    excluded = 0
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [], 0, ["%s: could not read %s (%s)" % (source.id, path.name, type(exc).__name__)]
    records, bad = _records(text, path.suffix.lower())
    if bad and not records and path.suffix.lower() == ".json":
        warnings.append("%s: %s is not a JSON array or object" % (source.id, path.name))
    elif bad:
        warnings.append("%s: skipped %d unreadable line(s) in %s" % (source.id, bad, path.name))
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            built = _entry(record, source, ctx)
        except ValueError:
            bad += 1
            continue
        if built is None:
            excluded += 1
        elif built:
            entries.append(built)
    if bad and path.suffix.lower() == ".json" and records:
        warnings.append("%s: skipped %d record(s) in %s" % (source.id, bad, path.name))
    return entries, excluded, warnings


def _records(text: str, suffix: str) -> tuple[list, int]:
    stripped = text.strip()
    if not stripped:
        return [], 0
    if suffix == ".json" or stripped.startswith("[") or stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            if suffix == ".jsonl" or "\n" in stripped:
                return _jsonl(text)
            return [], 1
        if isinstance(data, list):
            return data, 0
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data["entries"], 0
        if isinstance(data, dict) and _looks_like_entry(data):
            return [data], 0
        if suffix != ".jsonl":
            return [], 1
    return _jsonl(text)


def _jsonl(text: str) -> tuple[list, int]:
    rows = []
    bad = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    return rows, bad


def _looks_like_entry(data: dict) -> bool:
    return any(key in data for key in ("summary", "title", "project", "timestamp"))


def _entry(record: dict, source, ctx):
    start, end = _when(record, ctx.now)
    if not in_window(end, ctx.now, ctx.days):
        return False  # outside the window: not an exclusion
    raw_project = _first(record, "project", "repo", "name") or "(unknown)"
    title_raw = _first(record, "summary", "title", "text") or ""
    agent = _first(record, "agent", "role", "by") or ""
    status = _status(record.get("status", ""))
    files = _files(record)
    links = _links(record)
    blobs = [raw_project, title_raw, agent, " ".join(files)]
    if is_excluded(ctx.exclude_res, blobs):
        return None
    project = redact(display_project(str(raw_project), ctx.project_names)) or "(unknown)"
    title = title_from(str(title_raw)) or "(untitled)"
    agent_clean = redact(str(agent))[:60] if agent else ""
    if agent and redact(str(agent)) != str(agent):
        agent_clean = redact(str(agent))[:60]
    files_clean = []
    for item in files:
        short = redact(str(item))
        if short and short not in files_clean:
            files_clean.append(short)
    links_clean = []
    for link in links:
        cleaned = _clean_link(link)
        if cleaned:
            links_clean.append(cleaned)
    return make_entry(
        source=source.id,
        project=project,
        title=title,
        start=start,
        end=end,
        status=status,
        agent=agent_clean,
        links=links_clean,
        files=files_clean,
        files_total=len(files_clean),
        session_id=str(record.get("id") or "")[:80],
        detail="",
    )


def _when(record: dict, now: datetime) -> tuple[datetime, datetime]:
    end = _one_time(record, now, ("timestamp", "end", "at", "time"))
    start = _one_time(record, now, ("start",))
    if end is None and start is None:
        raise ValueError("missing time")
    if end is None:
        end = start
    if start is None:
        start = end
    assert start is not None and end is not None
    return start, end


def _one_time(record: dict, now: datetime, keys: tuple[str, ...]) -> datetime | None:
    date_hint = record.get("date")
    for key in keys:
        raw = record.get(key)
        if raw is None or raw == "":
            continue
        parsed = _parse_time(raw, date_hint, now)
        if parsed is not None:
            return parsed
    if date_hint and "time" not in keys and "timestamp" not in keys:
        return None
    if date_hint and not any(record.get(key) for key in keys):
        parsed = _parse_time(date_hint, None, now)
        if parsed is not None:
            return parsed.replace(hour=12, minute=0, second=0, microsecond=0)
    return None


def _parse_time(raw: object, date_hint: object, now: datetime) -> datetime | None:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        stamp = float(raw)
        if stamp > 10_000_000_000:  # milliseconds
            stamp /= 1000.0
        return datetime.fromtimestamp(stamp).astimezone(now.tzinfo)
    text = str(raw).strip()
    if not text:
        return None
    if _DATE.match(text) and date_hint is None:
        year, month, day = (int(part) for part in text.split("-"))
        return datetime(year, month, day, 12, 0, tzinfo=now.tzinfo)
    clock = _CLOCK.match(text)
    if clock and date_hint:
        day = _parse_time(date_hint, None, now)
        if day is None:
            return None
        hour = int(clock.group(1))
        minute = int(clock.group(2))
        second = int(clock.group(3) or 0)
        ampm = clock.group(4)
        if ampm:
            hour = hour % 12
            if ampm.lower() == "pm":
                hour += 12
        elif hour > 23:
            return None
        return day.replace(hour=hour, minute=minute, second=second, microsecond=0)
    try:
        return aware(parse_iso(text), now)
    except ValueError:
        return None


def _first(record: dict, *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _files(record: dict) -> list[str]:
    raw = record.get("files", record.get("files_written", []))
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item.strip()]


def _links(record: dict) -> list:
    raw = record.get("links", [])
    links = []
    if isinstance(raw, list):
        links.extend(raw)
    href = record.get("href")
    if isinstance(href, str):
        links.append({"href": href, "label": record.get("label") or href})
    return links


def _clean_link(link: object) -> dict | None:
    if isinstance(link, str):
        href, label = link, link
    elif isinstance(link, dict):
        href = link.get("href") or link.get("url") or ""
        label = link.get("label") or link.get("title") or ""
        if not isinstance(href, str):
            return None
        if not isinstance(label, str) or not label.strip():
            label = href
    else:
        return None
    kind = classify_href(href)
    if kind is None:
        return None
    mode, clean = kind
    if redact(clean) != clean or redact(label) != label:
        return None
    shown = redact(label).strip()[:80] or "link"
    return {"label": shown, "href": clean, "external": mode == "web"}


def classify_href(href: str) -> tuple[str, str] | None:
    """Return ('web'|'file', href) or None when the link is unsafe."""
    text = (href or "").strip()
    if not text or len(text) > 2000:
        return None
    lower = text.lower()
    if lower.startswith(("javascript:", "data:", "vbscript:", "file:")):
        return None
    if lower.startswith("http://") or lower.startswith("https://"):
        return "web", text
    if text.startswith("//") or text.startswith(("/", "\\")) or "\\" in text:
        return None
    parts = text.split("/")
    if any(part == ".." for part in parts):
        return None
    if ":" in parts[0]:
        return None
    return "file", text


def _status(raw: object) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str):
        return ""
    text = re.sub(r"\s+", " ", raw.strip().lower().replace("_", " ").replace("-", " "))
    if not text:
        return ""
    if text in ("done", "complete", "completed"):
        return "done"
    if text in ("waiting", "waiting on you", "waiting on me", "blocked", "needs you"):
        return "waiting"
    if text.startswith("waiting"):
        return "waiting"
    if text in ("in progress", "progress", "doing", "wip", "started"):
        return "progress"
    if redact(text) != text:
        return ""
    return text[:40]
