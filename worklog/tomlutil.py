"""A small TOML reader for worklog configs.

Covers the subset the example config uses: comments, basic and literal
strings, integers, booleans, arrays, tables, and arrays of tables.
Inline tables, floats, and dates are rejected with a clear error.
Python 3.9 has no tomllib, and this project stays on the standard library.
"""

from __future__ import annotations

import re
from pathlib import Path


class TomlError(ValueError):
    pass


class _Unterminated(Exception):
    pass


def load_toml(text: str, path: str | None = None) -> dict:
    lines = text.lstrip("\ufeff").splitlines()
    root: dict = {}
    current = root
    pending = ""
    pending_at = 1
    index = 0
    while index < len(lines):
        lineno = index + 1
        raw = lines[index]
        index += 1
        line = _strip_comment(raw)
        if pending:
            pending = (pending + " " + line).strip() if line else pending
            try:
                key, value = _parse_assignment(pending)
            except _Unterminated:
                continue
            except TomlError as exc:
                raise TomlError(_where(path, pending_at, exc)) from exc
            _assign(current, key, value, path, pending_at)
            pending = ""
            continue
        if not line:
            continue
        if line.startswith("[[") and line.endswith("]]"):
            name = line[2:-2].strip()
            current = _open_table(root, name, array=True, path=path, lineno=lineno)
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            current = _open_table(root, name, array=False, path=path, lineno=lineno)
            continue
        try:
            key, value = _parse_assignment(line)
        except _Unterminated:
            pending = line
            pending_at = lineno
            continue
        except TomlError as exc:
            raise TomlError(_where(path, lineno, exc)) from exc
        _assign(current, key, value, path, lineno)
    if pending:
        raise TomlError(_where(path, pending_at, "unterminated value"))
    return root


def _where(path: str | None, lineno: int, message: object) -> str:
    prefix = "%s:%d: " % (path or "config", lineno)
    return prefix + str(message)


def _strip_comment(line: str) -> str:
    out: list[str] = []
    in_str = False
    quote = ""
    escape = False
    for char in line:
        if in_str:
            out.append(char)
            if escape:
                escape = False
            elif char == "\\" and quote == '"':
                escape = True
            elif char == quote:
                in_str = False
            continue
        if char in "\"'":
            in_str = True
            quote = char
            out.append(char)
            continue
        if char == "#":
            break
        out.append(char)
    return "".join(out).strip()


def _assign(table: dict, key: str, value: object, path: str | None, lineno: int) -> None:
    if key in table:
        raise TomlError(_where(path, lineno, "duplicate key %r" % key))
    table[key] = value


def _key_parts(name: str) -> list[str]:
    parts: list[str] = []
    index = 0
    text = name.strip()
    if not text:
        raise TomlError("empty table name")
    while index < len(text):
        while index < len(text) and text[index] in " \t":
            index += 1
        if index >= len(text):
            break
        part, index = _parse_key(text, index)
        parts.append(part)
        while index < len(text) and text[index] in " \t":
            index += 1
        if index < len(text) and text[index] == ".":
            index += 1
            continue
        if index < len(text):
            raise TomlError("unexpected %r in table name" % text[index:])
    if not parts:
        raise TomlError("empty table name")
    return parts


def _open_table(root: dict, name: str, array: bool, path: str | None, lineno: int) -> dict:
    try:
        parts = _key_parts(name)
    except TomlError as exc:
        raise TomlError(_where(path, lineno, exc)) from exc
    node = root
    for part in parts[:-1]:
        nxt = node.get(part)
        if isinstance(nxt, list):
            if not nxt or not isinstance(nxt[-1], dict):
                raise TomlError(_where(path, lineno, "cannot nest under %r" % part))
            node = nxt[-1]
        elif isinstance(nxt, dict):
            node = nxt
        elif nxt is None:
            child: dict = {}
            node[part] = child
            node = child
        else:
            raise TomlError(_where(path, lineno, "cannot nest under %r" % part))
    last = parts[-1]
    if array:
        existing = node.get(last)
        if existing is None:
            existing = []
            node[last] = existing
        if not isinstance(existing, list):
            raise TomlError(_where(path, lineno, "%r is not a table array" % last))
        item: dict = {}
        existing.append(item)
        return item
    existing = node.get(last)
    if existing is None:
        child = {}
        node[last] = child
        return child
    if isinstance(existing, dict):
        return existing
    raise TomlError(_where(path, lineno, "%r is not a table" % last))


def _parse_assignment(text: str) -> tuple[str, object]:
    index = 0
    key, index = _parse_key(text, index)
    while index < len(text) and text[index] in " \t":
        index += 1
    if index >= len(text) or text[index] != "=":
        raise TomlError("expected '=' after %r" % key)
    index += 1
    value, index = _parse_value(text, index)
    rest = text[index:].strip()
    if rest:
        raise TomlError("unexpected %r after value" % rest)
    return key, value


def _parse_key(text: str, index: int) -> tuple[str, int]:
    while index < len(text) and text[index] in " \t":
        index += 1
    if index >= len(text):
        raise TomlError("expected a key")
    if text[index] == '"':
        return _parse_basic_string(text, index)
    if text[index] == "'":
        return _parse_literal_string(text, index)
    match = re.match(r"[A-Za-z0-9_-]+", text[index:])
    if not match:
        raise TomlError("expected a key")
    return match.group(0), index + match.end()


def _parse_value(text: str, index: int) -> tuple[object, int]:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    if index >= len(text):
        raise TomlError("missing value")
    char = text[index]
    if char == '"':
        return _parse_basic_string(text, index)
    if char == "'":
        return _parse_literal_string(text, index)
    if char == "[":
        return _parse_array(text, index)
    if char == "{":
        raise TomlError("inline tables are not supported; use [table] sections")
    end = index
    while end < len(text) and text[end] not in " \t\r\n,]":
        end += 1
    token = text[index:end]
    if token == "true":
        return True, end
    if token == "false":
        return False, end
    if re.fullmatch(r"-?\d+", token or ""):
        return int(token), end
    if token == "":
        raise TomlError("missing value")
    raise TomlError("unsupported value %r (strings, integers, booleans, arrays)" % token)


def _parse_basic_string(text: str, index: int) -> tuple[str, int]:
    if text[index] != '"':
        raise TomlError("expected a string")
    index += 1
    out: list[str] = []
    escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}
    while index < len(text):
        char = text[index]
        if char == "\n":
            raise TomlError("newlines inside strings are not supported")
        if char == '"':
            return "".join(out), index + 1
        if char == "\\":
            index += 1
            if index >= len(text):
                raise TomlError("bad escape")
            esc = text[index]
            if esc not in escapes:
                raise TomlError("unsupported escape \\%s" % esc)
            out.append(escapes[esc])
            index += 1
            continue
        out.append(char)
        index += 1
    raise TomlError("unterminated string")


def _parse_literal_string(text: str, index: int) -> tuple[str, int]:
    if text[index] != "'":
        raise TomlError("expected a string")
    index += 1
    end = text.find("'", index)
    if end < 0:
        raise TomlError("unterminated string")
    return text[index:end], end + 1


def _parse_array(text: str, index: int) -> tuple[list, int]:
    if text[index] != "[":
        raise TomlError("expected an array")
    index += 1
    items: list = []
    while True:
        while index < len(text) and text[index] in " \t\r\n,":
            index += 1
        if index >= len(text):
            raise _Unterminated()
        if text[index] == "]":
            return items, index + 1
        try:
            value, index = _parse_value(text, index)
        except _Unterminated:
            raise
        items.append(value)
        while index < len(text) and text[index] in " \t\r\n":
            index += 1
        if index >= len(text):
            raise _Unterminated()
        if text[index] == ",":
            index += 1
            continue
        if text[index] == "]":
            return items, index + 1
        raise TomlError("expected ',' or ']' in array")


def loads(text: str, path: Path | None = None) -> dict:
    return load_toml(text, str(path) if path else None)
