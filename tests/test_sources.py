"""Claude Code, generic JSON, and Claude desktop adapters."""

from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from worklog.sources.claude_code import extract_claude_code, scan_session
from worklog.sources.claude_desktop import extract_desktop
from worklog.sources.json_log import extract_json
from tests.support import NOW, context, source, write_jsonl

UTC = timezone.utc
LEAK = "TOOL_BODY_SHOULD_NOT_LEAK_44aa"


def _user(text, when, cwd, **extra):
    row = {
        "type": "user",
        "timestamp": when.isoformat(),
        "cwd": cwd,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }
    row.update(extra)
    return row


def _tool(name, path, when, cwd, body=LEAK, path_key="file_path"):
    return {
        "type": "assistant",
        "timestamp": when.isoformat(),
        "cwd": cwd,
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": name, "input": {path_key: path, "content": body, "new_string": body}}
            ],
        },
    }


class ClaudeCodeTests(unittest.TestCase):
    def test_summary_only_multiple_dirs_and_redaction(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = str(root / "client-a-site-audit")
            secret = "Rotate sk_" "live_abcdefghijklmnopqrstuvwxyz before sending"
            rows = [
                _user("Caveat: local disclaimer that is not the title.", NOW - timedelta(minutes=20), cwd),
                _user("sidechain prompt", NOW - timedelta(minutes=19), cwd, isSidechain=True),
                _user(secret, NOW - timedelta(minutes=18), cwd),
                _tool("Write", cwd + "/reports/audit.md", NOW - timedelta(minutes=10), cwd),
                _tool("str_replace", cwd + "/notes/sk_" "live_abcdefghijklmnopqrstuvwxyz.md", NOW - timedelta(minutes=5), cwd),
                {
                    "type": "custom-title",
                    "timestamp": (NOW - timedelta(minutes=1)).isoformat(),
                    "cwd": cwd,
                    "customTitle": "Custom title wins",
                },
            ]
            # custom title is last but should still win over the user text
            write_jsonl(root / "claude" / "projects" / "encoded" / "sess.jsonl", rows)
            other = str(root / "thursday-newsletter")
            write_jsonl(
                root / "claude-work" / "projects" / "news" / "sess2.jsonl",
                [_user("Outline the Thursday newsletter", NOW - timedelta(hours=2), other)],
            )
            nested = root / "claude" / "projects" / "encoded" / "sess" / "subagents" / "agent.jsonl"
            write_jsonl(nested, [_user("SUBAGENT_SHOULD_BE_IGNORED", NOW, cwd)])
            ctx = context(
                names={"client-a-site-audit": "Client A: Site audit"},
                home=root,
            )
            src = source("claude-code", [root / "claude", root / "claude-work"], "claude", "Claude")
            entries, excluded, warnings = extract_claude_code(src, ctx)
            self.assertEqual(excluded, 0)
            self.assertEqual(warnings, [])
            by_title = {entry["title"]: entry for entry in entries}
            self.assertIn("Custom title wins", by_title)
            self.assertNotIn(secret, json.dumps(entries))
            self.assertNotIn("sk_live_", json.dumps(entries))
            self.assertNotIn(LEAK, json.dumps(entries))
            self.assertNotIn("SUBAGENT_SHOULD_BE_IGNORED", json.dumps(entries))
            custom = by_title["Custom title wins"]
            self.assertEqual(custom["project"], "Client A: Site audit")
            self.assertIn("reports/audit.md", custom["files"])
            self.assertEqual(custom["detail"], "")
            work = by_title["Outline the Thursday newsletter"]
            self.assertEqual(work["detail"], "work")
            self.assertEqual(work["project"], "thursday-newsletter")

    def test_exclude_old_sessions_and_file_cap(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = "/home/demo/private-archive"
            write_jsonl(
                root / "claude" / "projects" / "private-archive" / "sess.jsonl",
                [_user("Index the binders", NOW, cwd)],
            )
            old_cwd = "/home/demo/old"
            old_path = root / "claude" / "projects" / "old" / "old.jsonl"
            write_jsonl(old_path, [_user("Archived kickoff", NOW - timedelta(days=40), old_cwd)])
            stale = root / "claude" / "projects" / "stale" / "stale.jsonl"
            write_jsonl(stale, [_user("Fresh mtime but we backdate the file", NOW, "/home/demo/stale")])
            os.utime(stale, (0, (NOW - timedelta(days=40)).timestamp()))
            many = "/home/demo/many"
            writes = [_user("Write a pile of notes", NOW - timedelta(hours=1), many)]
            for index in range(30):
                writes.append(_tool("Edit", "%s/n%d.txt" % (many, index), NOW, many, body="x"))
            write_jsonl(root / "claude" / "projects" / "many" / "many.jsonl", writes)
            ctx = context(patterns=[r"private-archive"])
            src = source("claude-code", [root / "claude"], "claude", "Claude")
            entries, excluded, _warnings = extract_claude_code(src, ctx)
            titles = [entry["title"] for entry in entries]
            self.assertNotIn("Index the binders", titles)
            self.assertNotIn("Archived kickoff", titles)
            self.assertNotIn("Fresh mtime but we backdate the file", titles)
            self.assertEqual(excluded, 1)
            pile = next(entry for entry in entries if entry["title"] == "Write a pile of notes")
            self.assertEqual(len(pile["files"]), 25)
            self.assertEqual(pile["files_total"], 30)
            blob = json.dumps(pile)
            self.assertNotIn(LEAK, blob)

    def test_notebook_path_and_home_shortening(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = str(root / "proj")
            outside = str(root / "other" / "b.md")
            rows = [
                _user("Edit the notebook", NOW - timedelta(minutes=5), cwd),
                _tool("NotebookEdit", str(root / "proj" / "notes.ipynb"), NOW, cwd, path_key="notebook_path"),
                _tool("Write", outside, NOW, cwd),
            ]
            path = root / "claude" / "projects" / "proj" / "sess.jsonl"
            write_jsonl(path, rows)
            ctx = context(home=root)
            entry = scan_session(path, "claude", "", ctx)
            self.assertIsInstance(entry, dict)
            self.assertIn("notes.ipynb", entry["files"])
            self.assertIn("~/other/b.md", entry["files"])


class JsonLogTests(unittest.TestCase):
    def test_jsonl_array_directory_and_clock_times(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(
                root / "logs" / "grok.jsonl",
                [
                    {
                        "timestamp": "2026-10-15T16:05:00+00:00",
                        "project": "Newsletter",
                        "summary": "Drafted Thursday issue",
                        "status": "waiting on you",
                        "agent": "Content Writer",
                        "links": [{"label": "draft", "href": "newsletter/draft.md"}],
                    },
                    {"timestamp": "2026-10-15T12:00:00+00:00", "summary": "this line is fine", "project": "Setup"},
                    "not json",
                ],
            )
            # A bad physical line: write it raw.
            with (root / "logs" / "grok.jsonl").open("a", encoding="utf-8") as handle:
                handle.write("{not json}\n")
            (root / "logs" / "batch.json").write_text(
                json.dumps(
                    [
                        {
                            "date": "2026-10-14",
                            "time": "4:05 PM",
                            "project": "Side project",
                            "summary": "Pick a domain",
                            "status": "in_progress",
                            "href": "javascript:alert(1)",
                        },
                        {
                            "date": "2026-09-01",
                            "time": "1:00 PM",
                            "project": "Old",
                            "summary": "Too old to show",
                            "status": "done",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            (root / "logs" / "wrapped.json").write_text(
                json.dumps({"entries": [{"timestamp": "2026-10-15T09:00:00+00:00", "project": "Setup", "summary": "Wrapped"}]}),
                encoding="utf-8",
            )
            ctx = context(patterns=["vault-notes"])
            src = source("json", [root / "logs"], "grok", "Grok Bot")
            entries, excluded, warnings = extract_json(src, ctx)
            titles = {entry["title"]: entry for entry in entries}
            self.assertIn("Drafted Thursday issue", titles)
            self.assertEqual(titles["Drafted Thursday issue"]["status"], "waiting")
            self.assertEqual(titles["Drafted Thursday issue"]["links"][0]["href"], "newsletter/draft.md")
            self.assertEqual(titles["Pick a domain"]["status"], "progress")
            self.assertEqual(titles["Pick a domain"]["links"], [])
            self.assertNotIn("Too old to show", titles)
            self.assertIn("Wrapped", titles)
            self.assertTrue(any("unreadable" in warning for warning in warnings))
            self.assertEqual(excluded, 0)

    def test_secret_summary_and_exclude(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [
                {
                    "timestamp": "2026-10-15T10:00:00+00:00",
                    "project": "Newsletter",
                    "summary": "The password = hunter2 stays out of the page",
                    "status": "done",
                    "links": [{"label": "pw", "href": "https://user:s3cret@example.com/x"}],
                },
                {
                    "timestamp": "2026-10-15T11:00:00+00:00",
                    "project": "vault-notes",
                    "summary": "Should be excluded entirely",
                    "status": "done",
                },
            ]
            path = root / "a.jsonl"
            write_jsonl(path, rows)
            ctx = context(patterns=["vault-notes"])
            entries, excluded, _warnings = extract_json(source("json", [path], "grok", "Grok"), ctx)
            self.assertEqual(excluded, 1)
            self.assertEqual(len(entries), 1)
            blob = json.dumps(entries)
            self.assertNotIn("hunter2", blob)
            self.assertNotIn("s3cret", blob)
            self.assertIn("[redacted]", entries[0]["title"])
            self.assertEqual(entries[0]["links"], [])

    def test_missing_file_warns(self):
        ctx = context()
        entries, _excluded, warnings = extract_json(
            source("json", [Path("/tmp/does-not-exist-worklog.jsonl")], "grok", "Grok"),
            ctx,
        )
        self.assertEqual(entries, [])
        self.assertTrue(warnings)


class DesktopTests(unittest.TestCase):
    def _meta(self, when, **extra):
        payload = {
            "title": "Sketch a fictional launch poster",
            "cliSessionId": "cli-1",
            "createdAt": (when - timedelta(hours=1)).timestamp() * 1000,
            "lastActivityAt": when.timestamp() * 1000,
            "userSelectedFolders": ["/home/demo/side-project"],
            "initialMessage": "UNIQUE_DESKTOP_BODY should not leak",
        }
        payload.update(extra)
        return payload

    def test_fixture_on_any_os(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "local-agent-mode-sessions" / "proj" / "sess" / "local_abc.json"
            meta.parent.mkdir(parents=True)
            meta.write_text(json.dumps(self._meta(NOW)), encoding="utf-8")
            transcript = meta.parent / "local_abc" / ".claude" / "projects" / "foo" / "cli-1.jsonl"
            cwd = "/home/demo/side-project"
            write_jsonl(
                transcript,
                [
                    _user("ignored because metadata has the title", NOW, cwd),
                    _tool("Write", cwd + "/poster.svg", NOW, cwd),
                    _tool("Write", "/sessions/sandbox/tmp.txt", NOW, cwd),
                ],
            )
            code = root / "claude-code-sessions" / "proj" / "sess" / "local_code.json"
            code.parent.mkdir(parents=True)
            code.write_text(
                json.dumps(
                    self._meta(
                        NOW - timedelta(hours=3),
                        title="Code tab note",
                        cliSessionId="cli-2",
                        userSelectedFolders=[],
                        originCwd="/home/demo/side-project",
                    )
                ),
                encoding="utf-8",
            )
            ctx = context(names={"side-project": "Side project"})
            entries, excluded, warnings = extract_desktop(
                source("claude-desktop", [root], "desktop", "Claude Desktop"),
                ctx,
            )
            self.assertEqual(excluded, 0)
            self.assertEqual(warnings, [])
            blob = json.dumps(entries)
            self.assertNotIn("UNIQUE_DESKTOP_BODY", blob)
            self.assertNotIn(LEAK, blob)
            cowork = next(entry for entry in entries if entry["detail"] == "cowork")
            self.assertEqual(cowork["project"], "Side project")
            self.assertEqual(cowork["title"], "Sketch a fictional launch poster")
            self.assertIn("poster.svg", cowork["files"])
            self.assertNotIn("/sessions/sandbox/tmp.txt", cowork["files"])
            tab = next(entry for entry in entries if entry["detail"] == "code tab")
            self.assertEqual(tab["title"], "Code tab note")

    def test_exclude_and_dedupe(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "local-agent-mode-sessions" / "proj" / "sess" / "local_abc.json"
            meta.parent.mkdir(parents=True)
            meta.write_text(
                json.dumps(self._meta(NOW, title="Notes for the private-archive")),
                encoding="utf-8",
            )
            ctx = context(patterns=["private-archive"])
            entries, excluded, _warnings = extract_desktop(
                source("claude-desktop", [root], "desktop", "Claude Desktop"),
                ctx,
            )
            self.assertEqual(entries, [])
            self.assertEqual(excluded, 1)
            meta.write_text(json.dumps(self._meta(NOW)), encoding="utf-8")
            ctx = context(seen={"cli-1"})
            entries, excluded, _warnings = extract_desktop(
                source("claude-desktop", [root], "desktop", "Claude Desktop"),
                ctx,
            )
            self.assertEqual(entries, [])
            self.assertEqual(excluded, 0)

    def test_default_path_is_skipped_off_macos(self):
        if sys.platform == "darwin":
            self.skipTest("default Claude desktop folder is readable on macOS")
        ctx = context()
        src = source(
            "claude-desktop",
            [Path.home() / "Library" / "Application Support" / "Claude"],
            "desktop",
            "Claude Desktop",
            explicit=False,
        )
        entries, _excluded, warnings = extract_desktop(src, ctx)
        self.assertEqual(entries, [])
        self.assertTrue(any("macOS" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
