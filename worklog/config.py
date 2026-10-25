"""Load a TOML or JSON work log config."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from worklog.ops import OpsError, default_ops_links, default_ops_steps, normalize_ops_links, normalize_ops_steps
from worklog.redact import compile_excludes
from worklog.tomlutil import TomlError, loads as load_toml

KINDS = ("claude-code", "json", "claude-desktop")
LOOPBACK = ("127.0.0.1", "localhost", "::1")


class ConfigError(Exception):
    pass


@dataclass
class Source:
    id: str
    label: str
    kind: str
    paths: list[Path]
    enabled: bool = True
    # False when paths were filled in from the kind's default locations.
    explicit_paths: bool = False


@dataclass
class Config:
    title: str
    days: int
    exclude: list[str]
    output: Path
    deliverables: Path | None
    host: str
    port: int
    project_names: dict[str, str]
    sources: list[Source]
    path: Path
    exclude_res: list = field(default_factory=list)
    ops_links: list = field(default_factory=list)
    ops_steps: list = field(default_factory=list)

    def source(self, source_id: str) -> Source | None:
        for item in self.sources:
            if item.id == source_id:
                return item
        return None


def default_config_path(cwd: Path | None = None) -> Path | None:
    base = cwd or Path.cwd()
    for name in ("worklog.toml", "worklog.json"):
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def load_config(path: Path) -> Config:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ConfigError("config not found: %s" % path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError("could not read %s: %s" % (path, exc)) from exc
    data = _parse_text(path, text)
    return _build(path, data)


def _parse_text(path: Path, text: str) -> dict:
    stripped = text.lstrip("\ufeff").lstrip()
    use_json = path.suffix.lower() == ".json" or stripped.startswith("{") or stripped.startswith("[")
    if use_json:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError("invalid JSON config %s: %s" % (path, exc)) from exc
    else:
        try:
            data = load_toml(text, path)
        except TomlError as exc:
            raise ConfigError(str(exc)) from exc
    if not isinstance(data, dict):
        raise ConfigError("config must be an object")
    return data


def _build(path: Path, data: dict) -> Config:
    base = path.parent
    title = _string(data.get("title", "Work Log"), "title") or "Work Log"
    days = data.get("days", 14)
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 366:
        raise ConfigError("days must be an integer from 1 to 366")
    exclude_raw = data.get("exclude", [])
    if not isinstance(exclude_raw, list) or not all(isinstance(item, str) for item in exclude_raw):
        raise ConfigError("exclude must be a list of strings")
    try:
        exclude_res = compile_excludes(list(exclude_raw))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    output = _resolve(base, _string(data.get("output", "site"), "output") or "site")
    deliverables = None
    if data.get("deliverables"):
        deliverables = _resolve(base, _string(data["deliverables"], "deliverables"))

    host = _string(data.get("host", "127.0.0.1"), "host") or "127.0.0.1"
    if host not in LOOPBACK:
        raise ConfigError("host must be 127.0.0.1, localhost, or ::1 (got %r)" % host)
    port = data.get("port", 8731)
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ConfigError("port must be an integer from 0 to 65535")

    names_raw = data.get("project_names", {})
    if not isinstance(names_raw, dict):
        raise ConfigError("project_names must be a table of strings")
    project_names = {}
    for key, value in names_raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ConfigError("project_names entries must be strings")
        project_names[key] = value

    sources_raw = data.get("sources", [])
    if not isinstance(sources_raw, list):
        raise ConfigError("sources must be a list")
    sources = [_source(base, item, index) for index, item in enumerate(sources_raw)]
    ids = [item.id for item in sources]
    if len(ids) != len(set(ids)):
        raise ConfigError("source ids must be unique")

    try:
        if "ops_links" in data:
            ops_links = normalize_ops_links(data.get("ops_links"))
        else:
            ops_links = default_ops_links()
        if "ops_steps" in data:
            ops_steps = normalize_ops_steps(data.get("ops_steps"))
        else:
            ops_steps = default_ops_steps()
    except OpsError as exc:
        raise ConfigError(str(exc)) from exc

    cfg = Config(
        title=title,
        days=days,
        exclude=list(exclude_raw),
        output=output,
        deliverables=deliverables,
        host=host,
        port=port,
        project_names=project_names,
        sources=sources,
        path=path,
        exclude_res=exclude_res,
        ops_links=ops_links,
        ops_steps=ops_steps,
    )
    return cfg


def _source(base: Path, item: object, index: int) -> Source:
    if not isinstance(item, dict):
        raise ConfigError("sources[%d] must be a table" % index)
    kind = _string(item.get("kind", ""), "sources[%d].kind" % index)
    if kind == "jsonl":
        kind = "json"
    if kind not in KINDS:
        raise ConfigError(
            "sources[%d].kind must be one of %s" % (index, ", ".join(KINDS))
        )
    source_id = _string(item.get("id", ""), "sources[%d].id" % index)
    if not source_id or not _SLUG.match(source_id):
        raise ConfigError(
            "sources[%d].id must be letters, numbers, '_' or '-' (got %r)" % (index, source_id)
        )
    label = _string(item.get("label", source_id), "sources[%d].label" % index) or source_id
    enabled = item.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError("sources[%d].enabled must be true or false" % index)
    if "paths" in item:
        paths_raw = item.get("paths")
    elif "path" in item:
        paths_raw = item.get("path")
    else:
        paths_raw = None
    explicit_paths = paths_raw is not None
    if isinstance(paths_raw, str):
        paths_raw = [paths_raw]
    if paths_raw is None:
        paths_raw = []
    if not isinstance(paths_raw, list) or not all(isinstance(p, str) for p in paths_raw):
        raise ConfigError("sources[%d].paths must be a list of strings" % index)
    paths = [_resolve(base, p) for p in paths_raw]
    if not paths:
        paths = _default_paths(kind)
        explicit_paths = False
    return Source(
        id=source_id,
        label=label,
        kind=kind,
        paths=paths,
        enabled=enabled,
        explicit_paths=explicit_paths,
    )


_SLUG = re.compile(r"^[A-Za-z0-9_-]+$")


def _default_paths(kind: str) -> list[Path]:
    home = Path.home()
    if kind == "claude-code":
        return [home / ".claude", home / ".claude-work"]
    if kind == "claude-desktop":
        return [home / "Library" / "Application Support" / "Claude"]
    return []


def _string(value: object, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ConfigError("%s must be a string" % name)
    return value.strip()


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()
