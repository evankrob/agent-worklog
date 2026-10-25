"""Default SEO Ops links and steps, and checks for custom ones.

The start page shows these when the config omits ``ops_links`` and
``ops_steps``. Custom values replace that list; they do not add to it.
Only http and https URLs are accepted, and anything that looks like a
secret is rejected.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from worklog.redact import redact

SEO_SKILLS_URL = "https://github.com/evankrob/seo-skills"
OPENLOCALSEO_URL = "https://github.com/evankrob/openlocalseo"
WORKLOG_URL = "https://github.com/evankrob/agent-worklog"
LOCAL_APP_URL = "http://localhost:5173"

# Names only. The page does not invent deep links for these.
OPS_SKILLS = (
    "seo-client-profile",
    "seo-audit-technical",
    "seo-audit-content",
    "seo-audit-local",
    "seo-audit-links",
    "seo-audit-report",
    "audit-to-tasks",
)

_DEFAULT_OPS_LINKS = (
    {
        "label": "SEO skills repo",
        "href": SEO_SKILLS_URL,
        "note": "Master SEO skill pipeline.",
    },
    {
        "label": "OpenLocalSEO repo",
        "href": OPENLOCALSEO_URL,
        "note": "Map-grid rank tracker. Quick start is on this page and in the README.",
    },
    {
        "label": "Work Log repo",
        "href": WORKLOG_URL,
        "note": "This start page.",
    },
)

_DEFAULT_OPS_STEPS = (
    "Clone or pull `evankrob/seo-skills`, then `pip install -r requirements.txt`. Keep run output outside the repo.",
    "Profile: `build_profile.py init`, then Evan approves, then `approve`.",
    "Technical audit: prefer Screaming Frog MCP when it is available, otherwise a Screaming Frog CSV, otherwise the built-in crawler. Use `--quick` for prospects.",
    "Content audit, after the crawl and GSC query×page data when that export is available.",
    "Local audit for client v1: pass `--citations-json`. Supply GBP with `--gbp-json` or the paid `--dataforseo-gbp` flag. Do not run `--grid` for client v1.",
    "Links audit from backlink exports. Repeat a prior run with `--prior-findings`.",
    "Assemble the report. Evan reviews it before it goes to the client.",
    "Run `audit_to_tasks` as a dry run only. Evan approves the preview before anything is sent to ClickUp.",
)

_LABEL_MAX = 120
_NOTE_MAX = 400
_STEP_MAX = 800
_HREF_MAX = 2000


class OpsError(ValueError):
    pass


def default_ops_links() -> list[dict]:
    return [dict(item) for item in _DEFAULT_OPS_LINKS]


def default_ops_steps() -> list[str]:
    return list(_DEFAULT_OPS_STEPS)


def web_href_ok(href: str) -> bool:
    """True for an http(s) URL with a host and no embedded password."""
    if not isinstance(href, str):
        return False
    text = href.strip()
    if not text or text != href or len(text) > _HREF_MAX:
        return False
    if any(ord(char) < 32 or char.isspace() for char in text):
        return False
    if "\\" in text:
        return False
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https"):
        return False
    if not parts.hostname or parts.username or parts.password:
        return False
    return True


def normalize_ops_links(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        raise OpsError("ops_links must be a list of tables")
    links = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise OpsError("ops_links[%d] must be a table" % index)
        label = _text(item.get("label", ""), "ops_links[%d].label" % index, _LABEL_MAX)
        href = _text(item.get("href", ""), "ops_links[%d].href" % index, _HREF_MAX)
        if "note" in item:
            note = _text(item.get("note", ""), "ops_links[%d].note" % index, _NOTE_MAX)
        else:
            note = ""
        if not label:
            raise OpsError("ops_links[%d].label is required" % index)
        if not web_href_ok(href):
            raise OpsError("ops_links[%d].href must be an http or https URL" % index)
        _reject_secret("ops_links[%d]" % index, label, href, note)
        links.append({"label": label, "href": href, "note": note})
    return links


def normalize_ops_steps(raw: object) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise OpsError("ops_steps must be a list of strings")
    steps = []
    for index, item in enumerate(raw):
        step = _text(item, "ops_steps[%d]" % index, _STEP_MAX)
        if not step:
            continue
        _reject_secret("ops_steps[%d]" % index, step)
        steps.append(step)
    return steps


def _text(value: object, name: str, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise OpsError("%s must be a string" % name)
    text = value.strip()
    if len(text) > limit:
        raise OpsError("%s must be %d characters or fewer" % (name, limit))
    return text


def _reject_secret(name: str, *parts: str) -> None:
    for part in parts:
        if redact(part) != part:
            raise OpsError("%s looks like it contains a secret" % name)
