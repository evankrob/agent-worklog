"""TOML subset and config loading."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from worklog.config import ConfigError, load_config
from worklog.tomlutil import TomlError, loads


SAMPLE = """
# comment
title = "Agent Team Work Log"
days = 7
host = "127.0.0.1"
port = 8731
output = "site"

exclude = [
  "private-archive",
  "vault",
]

[project_names]
client-a-site-audit = "Client A: Site audit"
"side project" = "Side project"

[[sources]]
id = "claude"
label = "Claude"
kind = "claude-code"
paths = ["fixtures/claude", "fixtures/claude-work"]

[[sources]]
id = "grok"
label = "Grok Bot"
kind = "json"
path = "logs/grok.jsonl"
enabled = true
"""


class TomlTests(unittest.TestCase):
    def test_sample_shape(self):
        data = loads(SAMPLE)
        self.assertEqual(data["title"], "Agent Team Work Log")
        self.assertEqual(data["days"], 7)
        self.assertEqual(data["exclude"], ["private-archive", "vault"])
        self.assertEqual(data["project_names"]["side project"], "Side project")
        self.assertEqual(len(data["sources"]), 2)
        self.assertEqual(data["sources"][1]["path"], "logs/grok.jsonl")
        self.assertIs(data["sources"][1]["enabled"], True)

    def test_strings_keep_hashes_and_escapes(self):
        data = loads('note = "a#b"\npath = "line\\nbreak"\nplain = \'# not a comment\'\n')
        self.assertEqual(data["note"], "a#b")
        self.assertEqual(data["path"], "line\nbreak")
        self.assertEqual(data["plain"], "# not a comment")

    def test_inline_comment_and_trailing_comma(self):
        data = loads('name = "ok" # trailing\nitems = ["a", "b",]\n')
        self.assertEqual(data["name"], "ok")
        self.assertEqual(data["items"], ["a", "b"])

    def test_duplicate_key_and_inline_table_fail(self):
        with self.assertRaises(TomlError):
            loads("a = 1\na = 2\n")
        with self.assertRaises(TomlError):
            loads("a = {b = 1}\n")

    def test_unterminated_string_fails(self):
        with self.assertRaises(TomlError):
            loads('a = "nope\n')


class ConfigTests(unittest.TestCase):
    def test_toml_and_json_resolve_next_to_the_config(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "worklog.toml").write_text(SAMPLE, encoding="utf-8")
            cfg = load_config(root / "worklog.toml")
            self.assertEqual(cfg.output, (root / "site").resolve())
            self.assertEqual(cfg.sources[0].id, "claude")
            self.assertEqual(cfg.sources[0].paths[0], (root / "fixtures" / "claude").resolve())
            self.assertTrue(cfg.sources[0].explicit_paths)
            self.assertEqual(cfg.project_names["client-a-site-audit"], "Client A: Site audit")
            payload = {
                "title": "From JSON",
                "days": 3,
                "sources": [{"id": "notes", "label": "Notes", "kind": "jsonl", "paths": ["notes.jsonl"]}],
            }
            (root / "worklog.json").write_text(json.dumps(payload), encoding="utf-8")
            jcfg = load_config(root / "worklog.json")
            self.assertEqual(jcfg.title, "From JSON")
            self.assertEqual(jcfg.sources[0].kind, "json")

    def test_rejects_bad_values(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "worklog.json"

            def check(payload, fragment):
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(ConfigError) as caught:
                    load_config(path)
                self.assertIn(fragment, str(caught.exception))

            check({"host": "0.0.0.0"}, "host")
            check({"days": 0, "sources": []}, "days")
            check({"port": 70000, "sources": []}, "port")
            check({"exclude": ["("], "sources": []}, "exclude")
            check(
                {"sources": [{"id": "a", "kind": "nope", "paths": ["x"]}]},
                "kind",
            )
            check(
                {
                    "sources": [
                        {"id": "a", "kind": "json", "paths": ["x"]},
                        {"id": "a", "kind": "json", "paths": ["y"]},
                    ]
                },
                "unique",
            )

    def test_omitted_claude_paths_are_defaults_and_not_explicit(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"sources": [{"id": "claude", "label": "Claude", "kind": "claude-code"}]}
            (root / "worklog.json").write_text(json.dumps(payload), encoding="utf-8")
            cfg = load_config(root / "worklog.json")
            self.assertFalse(cfg.sources[0].explicit_paths)
            self.assertEqual(cfg.sources[0].paths[0], Path.home() / ".claude")
            self.assertEqual(cfg.sources[0].paths[1], Path.home() / ".claude-work")

    def test_tilde_expands(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"sources": [{"id": "notes", "kind": "json", "paths": ["~/worklog-test-path"]}]}
            (root / "worklog.json").write_text(json.dumps(payload), encoding="utf-8")
            cfg = load_config(root / "worklog.json")
            self.assertEqual(cfg.sources[0].paths[0], (Path.home() / "worklog-test-path").resolve())


if __name__ == "__main__":
    unittest.main()
