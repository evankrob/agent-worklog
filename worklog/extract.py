"""Run configured sources and write a redacted log."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from worklog.config import Config
from worklog.model import window_bounds
from worklog.sources import ADAPTERS
from worklog.sources.claude_code import collect_session_ids


@dataclass
class Context:
    now: datetime
    days: int
    window_start: datetime
    exclude_res: list
    project_names: dict
    home: Path
    seen: set = field(default_factory=set)


def extract(cfg: Config, now: datetime | None = None) -> dict:
    if now is None:
        moment = datetime.now().astimezone()
    elif now.tzinfo is None:
        moment = now.astimezone()
    else:
        moment = now
    start, _end = window_bounds(moment, cfg.days)
    ctx = Context(
        now=moment,
        days=cfg.days,
        window_start=start,
        exclude_res=cfg.exclude_res,
        project_names=dict(cfg.project_names),
        home=Path.home(),
    )
    for source in cfg.sources:
        if source.enabled and source.kind == "claude-code":
            for directory in source.paths:
                ctx.seen.update(collect_session_ids(directory))
    entries: list[dict] = []
    warnings: list[str] = []
    summary: list[dict] = []
    enabled = []
    for source in cfg.sources:
        if not source.enabled:
            continue
        enabled.append(source)
        adapter = ADAPTERS[source.kind]
        found, excluded, warns = adapter(source, ctx)
        entries.extend(found)
        warnings.extend(warns)
        summary.append(
            {"id": source.id, "label": source.label, "kept": len(found), "excluded": excluded}
        )
    entries.sort(key=lambda item: item.get("end") or "", reverse=True)
    return {
        "generated": moment.isoformat(timespec="seconds"),
        "days": cfg.days,
        "title": cfg.title,
        "project_order": list(cfg.project_names.values()),
        "sources": [{"id": source.id, "label": source.label, "kind": source.kind} for source in enabled],
        "entries": entries,
        "warnings": warnings,
        "summary": summary,
    }


def write_log(document: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)
