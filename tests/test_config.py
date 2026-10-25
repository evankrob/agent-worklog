"""TOML subset and config loading."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from worklog.config import ConfigError, load_config
from worklog.ops import default_ops_links, default_ops_steps
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

    def test_ops_defaults_when_omitted_and_replacements_when_set(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "worklog.toml").write_text(SAMPLE, encoding="utf-8")
            cfg = load_config(root / "worklog.toml")
            self.assertEqual(cfg.ops_links, default_ops_links())
            self.assertEqual(cfg.ops_steps, default_ops_steps())
            self.assertEqual(len(cfg.ops_steps), 8)
            custom = """
title = "Work Log"
ops_steps = [
  "Only this step",
  " ",
]
[[ops_links]]
label = "Notes"
href = "https://example.com/notes"
note = "A note"

[[sources]]
id = "notes"
kind = "json"
paths = ["notes.jsonl"]
"""
            (root / "custom.toml").write_text(custom, encoding="utf-8")
            custom_cfg = load_config(root / "custom.toml")
            self.assertEqual(custom_cfg.ops_steps, ["Only this step"])
            self.assertEqual(
                custom_cfg.ops_links,
                [{"label": "Notes", "href": "https://example.com/notes", "note": "A note"}],
            )
            cleared = {"ops_steps": [], "ops_links": [], "sources": []}
            (root / "cleared.json").write_text(json.dumps(cleared), encoding="utf-8")
            cleared_cfg = load_config(root / "cleared.json")
            self.assertEqual(cleared_cfg.ops_steps, [])
            self.assertEqual(cleared_cfg.ops_links, [])

    def test_rejects_unsafe_ops_links(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "worklog.json"

            def check(payload, fragment):
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(ConfigError) as caught:
                    load_config(path)
                self.assertIn(fragment, str(caught.exception))

            check({"ops_links": [{"label": "x", "href": "javascript:alert(1)"}], "sources": []}, "href")
            check({"ops_links": [{"label": "x", "href": "file:///etc/passwd"}], "sources": []}, "href")
            check({"ops_links": [{"label": "x", "href": "https://user:pw@example.com/a"}], "sources": []}, "href")
            check({"ops_links": "https://example.com", "sources": []}, "ops_links")
            check({"ops_steps": [1], "sources": []}, "ops_steps")
            check(
                {"ops_links": [{"label": "x", "href": "https://example.com", "note": "password = hunter2"}], "sources": []},
                "secret",
            )

    def test_tilde_expands(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"sources": [{"id": "notes", "kind": "json", "paths": ["~/worklog-test-path"]}]}
            (root / "worklog.json").write_text(json.dumps(payload), encoding="utf-8")
            cfg = load_config(root / "worklog.json")
            self.assertEqual(cfg.sources[0].paths[0], (Path.home() / "worklog-test-path").resolve())


if __name__ == "__main__":
    unittest.main()
