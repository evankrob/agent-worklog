"""Own-project status board for the Projects tab.

The start page shows these when the config omits ``projects``. A custom
list replaces that one; it does not add to it. Only http and https URLs
are accepted, and anything that looks like a secret is rejected.

The built-in list is the own-product board as of 2026-10-27. Client work
is not included. One seed link (a GitHub commit URL whose SHA is 40 hex
characters) is omitted because the same secret check used for ops links
rejects it.
"""

from __future__ import annotations

import copy
import re
from datetime import date

from worklog.ops import web_href_ok
from worklog.redact import redact

STATUSES = ("active", "waiting", "blocked", "parked")

_NAME_MAX = 120
_STATE_MAX = 800
_LABEL_MAX = 120
_VALUE_MAX = 120
_WHAT_MAX = 400
_HREF_MAX = 2000
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLUG = re.compile(r"^[A-Za-z0-9_-]+$")

# Own products only. Do not add client work here.
_SEED = [
    {
        "id": "golf-cart-racer",
        "name": "Golf Cart Racer",
        "status": "active",
        "state": (
            "Live — Hole 2 leaderboard ties + weekly/all-time tip shipped (PR #35). "
            "Waiting on Evan for name→profile/career stats and shortcut-reduction plan."
        ),
        "links": [
            {"label": "Live", "href": "https://golfcartrace.com"},
            {"label": "Repo", "href": "https://github.com/evankrob/golf-cart-racer"},
            {"label": "PR #35", "href": "https://github.com/evankrob/golf-cart-racer/pull/35"},
        ],
        "metrics": [
            {"label": "Holes", "value": "3"},
            {"label": "Latest", "value": "PR #35"},
        ],
        "timeline": [
            {"when": "2026-10-27", "what": "PR #35 squash-merged — competition-rank Tie + tip"},
            {"when": "2026-10-19", "what": "M4 sound/medals/short ghosts live"},
            {"when": "2026-10-18", "what": "M6 drift + boost strips live"},
        ],
    },
    {
        "id": "what-you-missed",
        "name": "What You Missed",
        "status": "blocked",
        "state": (
            "Site live on whatyoumissed.online (Oct 26 issue up). "
            "List signup returns 503 — Kit + CAN-SPAM address still blocked before any send."
        ),
        "links": [
            {"label": "Site", "href": "https://whatyoumissed.online"},
            {"label": "Oct 26 issue", "href": "https://whatyoumissed.online/issues/2026-10-26/"},
            {"label": "Workers backup", "href": "https://whatyoumissed.evan-fde.workers.dev"},
        ],
        "metrics": [
            {"label": "Issues live", "value": "2+"},
            {"label": "List", "value": "HOLD"},
        ],
        "timeline": [
            {"when": "2026-10-26", "what": "Custom domain live; Oct 26 issue published"},
            {"when": "2026-10-19", "what": "Oct 19 issue in Past Issues"},
        ],
    },
    {
        "id": "seo-notebook",
        "name": "SEO Notebook",
        "status": "waiting",
        "state": (
            "Public main has live GSC/GA4 SA connectors. "
            "Fillungo deploy waiting on Evan for R2 on Scott's Cloudflare; then seed CPI, WMD, Whilden, Passage."
        ),
        "links": [
            {"label": "Repo (public)", "href": "https://github.com/evankrob/seo-notebook"},
        ],
        "metrics": [
            {"label": "Clients to seed", "value": "4"},
            {"label": "Blocker", "value": "R2"},
        ],
        "timeline": [
            {"when": "2026-10-27", "what": "Prefer SA over clients@ OAuth; Evan admins via evan@fillungo.co"},
            {"when": "2026-10-18", "what": "Phase 1 deployed with mock data"},
        ],
    },
    {
        "id": "openlocalseo",
        "name": "OpenLocalSEO",
        "status": "waiting",
        "state": (
            "Live behind Cloudflare Access with real DataForSEO. "
            "Waiting on Evan's last Local Dominator export before cancelling LD."
        ),
        "links": [
            {"label": "App", "href": "https://openlocalseo.evan-fde.workers.dev/"},
            {"label": "Repo", "href": "https://github.com/evankrob/openlocalseo"},
        ],
        "metrics": [
            {"label": "Data", "value": "DataForSEO"},
            {"label": "Auth", "value": "CF Access"},
        ],
        "timeline": [
            {"when": "2026-10-18", "what": "Heatmap + scan fixes shipped (PRs #1–#8)"},
        ],
    },
    {
        "id": "computer-poll",
        "name": "The Computer Poll",
        "status": "active",
        "state": "Running — weekly rankings site + @AIPollCFB reply/growth routines. No open Evan blockers.",
        "links": [
            {"label": "Site", "href": "https://thecomputerpoll.com"},
            {"label": "X", "href": "https://x.com/AIPollCFB"},
        ],
        "metrics": [
            {"label": "Routines", "value": "Mon recap + daily replies"},
        ],
        "timeline": [
            {"when": "2026-10-15", "what": "Known slip: BYU location wrong in a reply (left up)"},
        ],
    },
    {
        "id": "agent-worklog",
        "name": "Agent Worklog",
        "status": "active",
        "state": (
            "Public MIT dashboard; Work + SEO Ops tabs live on box :8770 and Mac :8731. "
            "This PR adds Projects."
        ),
        "links": [
            {"label": "Repo", "href": "https://github.com/evankrob/agent-worklog"},
        ],
        "metrics": [
            {"label": "Tabs now", "value": "Work · SEO Ops"},
        ],
        "timeline": [
            {"when": "2026-10-25", "what": "SEO Ops tab squash-merged"},
            {"when": "2026-10-19", "what": "Repo went public"},
        ],
    },
    {
        "id": "stayfairly",
        "name": "StayFairly",
        "status": "parked",
        "state": (
            "Evan likes this one; only project on paid Supabase. "
            "Brain dump: build more pages, agent-friendly trip watching, owner open-week discounts. "
            "Status beyond brain dump: unknown."
        ),
        "links": [],
        "metrics": [
            {"label": "Hosting note", "value": "Paid Supabase"},
        ],
        "timeline": [],
    },
    {
        "id": "locallab",
        "name": "LocalLab",
        "status": "parked",
        "state": "Paid review-gathering tool that isn't used or marketed. Hook idea: review velocity (ratingcaptain.com lead magnet).",
        "links": [],
        "metrics": [],
        "timeline": [],
    },
    {
        "id": "seo-skills",
        "name": "seo-skills (audit pipeline)",
        "status": "active",
        "state": (
            "PR #10 merged (PSI key, count-aware titles, location NAP). "
            "Human HTML deliverable prototype ready for Evan. PROCESS-EVAL do-now still optional."
        ),
        "links": [
            {"label": "Repo", "href": "https://github.com/evankrob/seo-skills"},
            {"label": "PR #10", "href": "https://github.com/evankrob/seo-skills/pull/10"},
        ],
        "metrics": [
            {"label": "Latest", "value": "8ec3f87"},
            {"label": "CPI findings", "value": "41"},
        ],
        "timeline": [
            {"when": "2026-10-27", "what": "PR #10 squash-merged; human HTML prototype"},
            {"when": "2026-10-27", "what": "PR #9 trust fixes merged"},
        ],
    },
]


class ProjectsError(ValueError):
    pass


def default_projects() -> list[dict]:
    return copy.deepcopy(_DEFAULT_PROJECTS)


def normalize_projects(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        raise ProjectsError("projects must be a list of tables")
    projects = []
    seen = set()
    for index, item in enumerate(raw):
        projects.append(_project(item, index, seen))
    return projects


def _project(item: object, index: int, seen: set) -> dict:
    prefix = "projects[%d]" % index
    if not isinstance(item, dict):
        raise ProjectsError("%s must be a table" % prefix)
    project_id = _text(item.get("id", ""), prefix + ".id", _NAME_MAX)
    if not project_id or not _SLUG.match(project_id):
        raise ProjectsError(
            "%s.id must be letters, numbers, '_' or '-' (got %r)" % (prefix, project_id)
        )
    if project_id in seen:
        raise ProjectsError("project ids must be unique (duplicate %r)" % project_id)
    seen.add(project_id)
    name = _text(item.get("name", ""), prefix + ".name", _NAME_MAX)
    if not name:
        raise ProjectsError("%s.name is required" % prefix)
    status = _text(item.get("status", ""), prefix + ".status", 40).lower()
    if status not in STATUSES:
        raise ProjectsError(
            "%s.status must be %s" % (prefix, ", ".join(STATUSES))
        )
    state = _text(item.get("state", ""), prefix + ".state", _STATE_MAX)
    if not state:
        raise ProjectsError("%s.state is required" % prefix)
    updated = _day(item.get("updated", ""), prefix + ".updated") if "updated" in item else ""
    links = _rows(item.get("links", []), prefix + ".links", _link)
    metrics = _rows(item.get("metrics", []), prefix + ".metrics", _metric)
    timeline = _rows(item.get("timeline", []), prefix + ".timeline", _event)
    _reject_secret(prefix, name, state, updated)
    return {
        "id": project_id,
        "name": name,
        "status": status,
        "state": state,
        "updated": updated,
        "links": links,
        "metrics": metrics,
        "timeline": timeline,
    }


def _rows(raw: object, name: str, parse) -> list:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ProjectsError("%s must be a list of tables" % name)
    rows = []
    for index, item in enumerate(raw):
        rows.append(parse(item, "%s[%d]" % (name, index)))
    return rows


def _link(item: object, name: str) -> dict:
    if not isinstance(item, dict):
        raise ProjectsError("%s must be a table" % name)
    label = _text(item.get("label", ""), name + ".label", _LABEL_MAX)
    href = _text(item.get("href", ""), name + ".href", _HREF_MAX)
    if not label:
        raise ProjectsError("%s.label is required" % name)
    if not web_href_ok(href):
        raise ProjectsError("%s.href must be an http or https URL" % name)
    _reject_secret(name, label, href)
    return {"label": label, "href": href}


def _metric(item: object, name: str) -> dict:
    if not isinstance(item, dict):
        raise ProjectsError("%s must be a table" % name)
    label = _text(item.get("label", ""), name + ".label", _LABEL_MAX)
    value = _text(item.get("value", ""), name + ".value", _VALUE_MAX)
    if not label:
        raise ProjectsError("%s.label is required" % name)
    if not value:
        raise ProjectsError("%s.value is required" % name)
    _reject_secret(name, label, value)
    return {"label": label, "value": value}


def _event(item: object, name: str) -> dict:
    if not isinstance(item, dict):
        raise ProjectsError("%s must be a table" % name)
    when = _day(item.get("when", ""), name + ".when")
    what = _text(item.get("what", ""), name + ".what", _WHAT_MAX)
    if not when:
        raise ProjectsError("%s.when is required" % name)
    if not what:
        raise ProjectsError("%s.what is required" % name)
    _reject_secret(name, when, what)
    return {"when": when, "what": what}


def _day(value: object, name: str) -> str:
    if value is None:
        return ""
    text = _text(value, name, 40)
    if not text:
        return ""
    if not _DAY.match(text):
        raise ProjectsError("%s must be an ISO date (YYYY-MM-DD)" % name)
    try:
        date.fromisoformat(text)
    except ValueError:
        raise ProjectsError("%s must be an ISO date (YYYY-MM-DD)" % name) from None
    return text


def _text(value: object, name: str, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProjectsError("%s must be a string" % name)
    text = value.strip()
    if len(text) > limit:
        raise ProjectsError("%s must be %d characters or fewer" % (name, limit))
    return text


def _reject_secret(name: str, *parts: str) -> None:
    for part in parts:
        if redact(part) != part:
            raise ProjectsError("%s looks like it contains a secret" % name)


_DEFAULT_PROJECTS = normalize_projects(_SEED)
