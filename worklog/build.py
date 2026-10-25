"""Turn a redacted log into a static site and copy linked deliverables."""

from __future__ import annotations

import shutil
from pathlib import Path

from worklog.config import Config
from worklog.extract import extract, write_log
from worklog.model import FILES_DISPLAY
from worklog.render import render_html
from worklog.sources.json_log import classify_href


def build_site(cfg: Config, now=None) -> Path:
    document = extract(cfg, now=now)
    root = cfg.deliverables.resolve() if cfg.deliverables else None
    for entry in document["entries"]:
        _attach_deliverable_links(entry, root)
        _drop_unsafe_links(entry)
    destination = cfg.output
    destination.mkdir(parents=True, exist_ok=True)
    copied = _copy_deliverables(document["entries"], root, destination)
    # UI config, not part of the redacted log written beside the page.
    document["ops_links"] = [dict(item) for item in cfg.ops_links]
    document["ops_steps"] = list(cfg.ops_steps)
    page = render_html(document)
    (destination / "index.html").write_text(page, encoding="utf-8")
    public = {
        key: document[key]
        for key in ("generated", "days", "title", "sources", "entries", "warnings")
    }
    # The served log is the same redacted summary. It has no transcript bodies.
    write_log(public, destination / "log.json")
    document["copied"] = copied
    return destination, document


def _drop_unsafe_links(entry: dict) -> None:
    kept = []
    for link in entry.get("links") or []:
        if not isinstance(link, dict):
            continue
        href = link.get("href") or ""
        kind = classify_href(href)
        if kind is None:
            continue
        mode, clean = kind
        label = (link.get("label") or clean).strip()[:80] or "link"
        kept.append({"label": label, "href": clean, "external": mode == "web" or bool(link.get("external"))})
    entry["links"] = kept


def _attach_deliverable_links(entry: dict, root: Path | None) -> None:
    if root is None or not root.is_dir():
        return
    links = entry.setdefault("links", [])
    known = {link.get("href") for link in links if isinstance(link, dict)}
    for rel in entry.get("files") or []:
        if rel in known or classify_href(rel) != ("file", rel):
            continue
        src = _inside(root, rel)
        if src is None:
            continue
        links.append({"label": Path(rel).name, "href": rel, "external": False})
        known.add(rel)


def _copy_deliverables(entries: list[dict], root: Path | None, destination: Path) -> int:
    if root is None or not root.is_dir():
        return 0
    copied = 0
    seen: set[str] = set()
    for entry in entries:
        for link in entry.get("links") or []:
            if link.get("external"):
                continue
            href = link.get("href") or ""
            if href in seen:
                continue
            src = _inside(root, href)
            if src is None:
                continue
            target = destination / href
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            seen.add(href)
            copied += 1
        shown = 0
        for rel in entry.get("files") or []:
            if shown >= FILES_DISPLAY:
                break
            shown += 1
    return copied


def _inside(root: Path, rel: str) -> Path | None:
    kind = classify_href(rel)
    if kind != ("file", rel):
        return None
    try:
        src = (root / rel).resolve()
        src.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    if not src.is_file():
        return None
    return src
