"""Dashboard HTML, deliverable copy, local server, and the demo pipeline."""

from __future__ import annotations

import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import urlopen

from worklog.build import build_site
from worklog.config import load_config
from worklog.demo_data import (
    AUDIT_TITLE,
    EXCLUDED_TITLE,
    LEAK,
    OLD_TITLE,
    SUBAGENT,
    materialize,
)
from worklog.render import render_html
from worklog.serve import ensure_loopback, start_server
from worklog.config import ConfigError

UTC = timezone.utc
NOW = datetime(2026, 10, 15, 21, 0, tzinfo=UTC)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _entry(**kwargs):
    base = {
        "source": "claude",
        "project": "Newsletter",
        "title": "Drafted the issue",
        "start": _iso(NOW - timedelta(minutes=30)),
        "end": _iso(NOW - timedelta(minutes=10)),
        "status": "done",
        "agent": "Content Writer",
        "links": [],
        "files": [],
        "files_total": 0,
        "detail": "",
    }
    base.update(kwargs)
    return base


def _doc(entries, sources=None, project_order=None, days=14):
    return {
        "generated": _iso(NOW),
        "days": days,
        "title": "Agent Team Work Log",
        "project_order": project_order or [],
        "sources": sources
        or [
            {"id": "claude", "label": "Claude", "kind": "claude-code"},
            {"id": "grok", "label": "Grok Bot", "kind": "json"},
        ],
        "entries": entries,
    }


class RenderTests(unittest.TestCase):
    def test_columns_waiting_list_and_no_totals(self):
        entries = [
            _entry(
                title="Technical audit",
                project="Client A: Site audit",
                start=_iso(NOW.replace(hour=20, minute=42)),
                end=_iso(NOW.replace(hour=20, minute=55)),
                status="",
                agent="",
                files=["reports/audit.md", "reports/extra.md"],
                files_total=4,
                links=[{"label": "audit.md", "href": "reports/audit.md", "external": False}],
            ),
            _entry(
                source="grok",
                project="Client A: Site audit",
                title="Approve the prioritized fix list",
                status="waiting",
                agent="",
                start=_iso(NOW.replace(hour=19, minute=10)),
                end=_iso(NOW.replace(hour=19, minute=10)),
            ),
            _entry(
                source="grok",
                project="Newsletter",
                title="Drafted Thursday issue",
                end=_iso(NOW - timedelta(days=1, hours=2)),
                start=_iso(NOW - timedelta(days=1, hours=2)),
                status="progress",
            ),
            _entry(
                source="claude",
                project="Setup",
                title="Older note",
                end=_iso(NOW - timedelta(days=2)),
                start=_iso(NOW - timedelta(days=2)),
                status="done",
            ),
        ]
        html = render_html(
            _doc(entries, project_order=["Client A: Site audit", "Newsletter", "Setup"])
        )
        self.assertIn("<h3>Claude</h3>", html)
        self.assertIn("<h3>Grok Bot</h3>", html)
        self.assertIn("Technical audit", html)
        self.assertIn("8:42–8:55 PM", html)
        self.assertIn(">Today<", html)
        self.assertIn(">Yesterday<", html)
        self.assertIn("Tue Oct 13 2026", html)
        self.assertIn("waiting on you", html)
        self.assertIn("in progress", html)
        self.assertIn('class="st progress"', html)
        self.assertNotIn("Waiting on you (", html)
        self.assertNotIn("total", html.lower())
        self.assertNotRegex(html, r"\d+ (entries|sessions)")
        # Chip order follows the config, with All first.
        self.assertLess(html.index("Client A: Site audit"), html.index(">Newsletter<"))
        self.assertLess(html.index('data-project="All"'), html.index('data-project="Client A: Site audit"'))
        # Grouped under the project heading inside the Claude column.
        claude = html.split('data-source="claude"')[1].split('data-source="grok"')[0]
        self.assertLess(claude.index("Client A: Site audit"), claude.index("Technical audit"))
        self.assertIn("reports/extra.md", html)
        self.assertIn("+2 more", html)
        self.assertIn('href="reports/audit.md"', html)
        self.assertIn("@media (max-width: 760px)", html)
        self.assertIn(".n2 { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }", html)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", html)
        self.assertIn('class="cols n2"', html)
        self.assertIn('html[data-theme="dark"]', html)
        self.assertIn("prefers-color-scheme: dark", html)
        self.assertIn("Grok Bot", html)
        wait = html.split('<section class="wait"')[1].split("</section>")[0]
        self.assertIn("Grok Bot", wait)
        self.assertNotIn(">grok<", wait)

    def test_escapes_markup_and_external_links(self):
        html = render_html(
            _doc(
                [
                    _entry(
                        title='</script><b>pwned</b>',
                        links=[{"label": "brief", "href": "https://example.com/brief", "external": True}],
                    )
                ]
            )
        )
        self.assertNotIn("<b>pwned</b>", html)
        self.assertIn("&lt;/script&gt;", html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn('target="_blank"', html)

    def test_empty_state(self):
        html = render_html(_doc([]))
        self.assertIn("Nothing in the last 14 days.", html)
        self.assertNotIn("<h3>", html)


class BuildAndServeTests(unittest.TestCase):
    def test_demo_pipeline_strips_private_content_and_copies_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = materialize(root, now=NOW)
            cfg = load_config(config_path)
            destination, document = build_site(cfg, now=NOW)
            html = (destination / "index.html").read_text(encoding="utf-8")
            log = (destination / "log.json").read_text(encoding="utf-8")
            self.assertIn(AUDIT_TITLE, html)
            self.assertIn("Agent Team Work Log", html)
            self.assertIn("<h3>Claude</h3>", html)
            self.assertIn("<h3>Grok Bot</h3>", html)
            for secret in (LEAK, EXCLUDED_TITLE, SUBAGENT, OLD_TITLE):
                self.assertNotIn(secret, html)
                self.assertNotIn(secret, log)
            self.assertTrue((destination / "reports" / "audit.md").is_file())
            self.assertTrue((destination / "preview" / "index.html").is_file())
            self.assertTrue((destination / "newsletter" / "draft.md").is_file())
            self.assertGreaterEqual(document["copied"], 6)
            # Absolute paths from the fixtures are not required on the page.
            self.assertNotIn("/home/demo/", html)
            self.assertNotIn("Waiting on you (", html)

    def test_traversal_is_not_copied(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "secret.txt"
            outside.write_text("DO_NOT_COPY", encoding="utf-8")
            deliverables = root / "deliverables"
            deliverables.mkdir()
            (deliverables / "ok.md").write_text("hello", encoding="utf-8")
            config = {
                "title": "Work Log",
                "days": 14,
                "output": "site",
                "deliverables": "deliverables",
                "sources": [
                    {
                        "id": "notes",
                        "label": "Notes",
                        "kind": "json",
                        "paths": ["notes.jsonl"],
                    }
                ],
            }
            (root / "notes.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": _iso(NOW),
                        "project": "Setup",
                        "summary": "Linked a file",
                        "status": "done",
                        "links": [
                            {"label": "ok", "href": "ok.md"},
                            {"label": "nope", "href": "../secret.txt"},
                            {"label": "abs", "href": "/etc/passwd"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "worklog.json").write_text(json.dumps(config), encoding="utf-8")
            cfg = load_config(root / "worklog.json")
            destination, _document = build_site(cfg, now=NOW)
            html = (destination / "index.html").read_text(encoding="utf-8")
            self.assertTrue((destination / "ok.md").is_file())
            self.assertFalse((destination / "secret.txt").exists())
            self.assertNotIn("DO_NOT_COPY", html)
            self.assertNotIn("../secret.txt", html)
            self.assertNotIn("/etc/passwd", html)
            self.assertIn('href="ok.md"', html)

    def test_server_is_loopback_and_serves_the_page(self):
        with self.assertRaises(ConfigError):
            ensure_loopback("0.0.0.0")
        self.assertEqual(ensure_loopback("localhost"), "127.0.0.1")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            materialize(root, now=NOW)
            cfg = load_config(root / "worklog.toml")
            destination, _document = build_site(cfg, now=NOW)
            server = start_server(destination, "127.0.0.1", 0)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen("http://127.0.0.1:%d/" % port, timeout=5) as response:
                    body = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200)
                    self.assertIn("no-store", response.headers.get("Cache-Control", ""))
                self.assertIn(AUDIT_TITLE, body)
                with urlopen("http://127.0.0.1:%d/reports/audit.md" % port, timeout=5) as response:
                    self.assertIn(b"Site audit", response.read())
                try:
                    urlopen("http://127.0.0.1:%d/reports/" % port, timeout=5)
                    self.fail("directory listing should be hidden")
                except HTTPError as exc:
                    self.assertEqual(exc.code, 404)
            finally:
                server.shutdown()
                server.server_close()


class ExtensionTests(unittest.TestCase):
    def test_manifest_is_local_mv3(self):
        root = Path(__file__).resolve().parents[1] / "extension"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["chrome_url_overrides"]["newtab"], "newtab.html")
        self.assertIn("storage", manifest["permissions"])
        blob = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*") if path.suffix in {".html", ".js", ".json"})
        self.assertNotIn("http://example", blob)
        self.assertIn("127.0.0.1", blob)
        self.assertNotIn("<script src=\"http", blob)


if __name__ == "__main__":
    unittest.main()
