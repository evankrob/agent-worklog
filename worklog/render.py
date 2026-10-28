"""Render the redacted log as one static HTML page.

The page is self-contained: no remote fonts, scripts, or images. The
browser only toggles the theme, the project chips, the Work / SEO Ops /
Projects tabs, and which project is open. Those controls show or hide markup
that is already in the file.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from worklog.model import FILES_DISPLAY, aware, parse_iso, window_bounds
from worklog.ops import (
    LOCAL_APP_URL,
    OPENLOCALSEO_URL,
    OPS_SKILLS,
    SEO_SKILLS_URL,
    default_ops_links,
    default_ops_steps,
)
from worklog.projects import default_projects

_ACCENTS = ("a0", "a1", "a2", "a3", "a4", "a5")

_STATUS_LABEL = {
    "done": "done",
    "waiting": "waiting on you",
    "progress": "in progress",
}


def render_html(document: dict) -> str:
    now = parse_iso(document["generated"])
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.now().astimezone().tzinfo)
    sources = list(document.get("sources") or [])
    entries = list(document.get("entries") or [])
    title = document.get("title") or "Work Log"
    days = int(document.get("days") or 14)
    projects = _project_chips(entries, document.get("project_order") or [])
    waiting = [entry for entry in entries if entry.get("status") == "waiting"]
    waiting.sort(key=lambda entry: entry.get("end") or "", reverse=True)
    days_html = _days_html(entries, sources, now)
    links = document["ops_links"] if "ops_links" in document else default_ops_links()
    steps = document["ops_steps"] if "ops_steps" in document else default_ops_steps()
    board = document["projects"] if "projects" in document else default_projects()
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="referrer" content="no-referrer">',
        '<meta name="robots" content="noindex">',
        '<meta name="theme-color" content="#f3f1eb">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'unsafe-inline\'; img-src \'self\' data:; base-uri \'none\'; form-action \'none\'">',
        "<title>%s</title>" % esc(title),
        '<link rel="icon" href="%s">' % _FAVICON,
        "<script>%s</script>" % _HEAD_SCRIPT,
        "<style>%s\n%s</style>" % (_CSS, _project_pick_css(board)),
        "</head>",
        '<body class="%s">' % ("wide" if len(sources) >= 3 else ""),
        '<header class="top">',
        "<div>",
        "<h1>%s</h1>" % esc(title),
        '<p class="sub">%s</p>' % esc(_subtitle(now, days)),
        "</div>",
        '<button type="button" id="theme" aria-pressed="false">Dark</button>',
        "</header>",
        '<div class="views" role="tablist" aria-label="Views">',
        '<button type="button" class="view on" id="tab-work" data-view-tab="work" role="tab" aria-selected="true" aria-controls="view-work">Work</button>',
        '<button type="button" class="view" id="tab-ops" data-view-tab="ops" role="tab" aria-selected="false" aria-controls="view-ops" tabindex="-1">SEO Ops</button>',
        '<button type="button" class="view" id="tab-projects" data-view-tab="projects" role="tab" aria-selected="false" aria-controls="view-projects" tabindex="-1">Projects</button>',
        "</div>",
        '<div id="view-work" role="tabpanel" aria-labelledby="tab-work">',
    ]
    if not entries:
        parts.append('<p class="empty-page">Nothing in the last %d days.</p>' % days)
    else:
        parts.append('<div class="chips" role="toolbar" aria-label="Projects">')
        parts.append(
            '<button type="button" class="chip on" data-project="All" aria-pressed="true">All</button>'
        )
        for project in projects:
            parts.append(
                '<button type="button" class="chip" data-project="%s" aria-pressed="false">%s</button>'
                % (esc(project), esc(project))
            )
        parts.append("</div>")
        labels = {source["id"]: source.get("label") or source["id"] for source in sources}
        parts.append(_waiting_html(waiting, labels))
        parts.append('<main id="days">%s</main>' % days_html)
        parts.append(
            '<p class="empty-page" id="empty-filter" hidden>Nothing in this project for the last %d days.</p>'
            % days
        )
    parts.append("</div>")
    parts.append(_ops_html(links, steps))
    parts.append(_projects_html(board))
    parts.append("<script>%s</script>" % _FILTER_SCRIPT)
    parts.append("</body></html>\n")
    return "\n".join(parts)


def _ops_html(links: list, steps: list) -> str:
    items = []
    for link in links or []:
        if not isinstance(link, dict):
            continue
        href = link.get("href") or ""
        label = link.get("label") or href or "link"
        note = link.get("note") or ""
        note_html = '<span class="ops-note">%s</span>' % _rich(note) if note else ""
        items.append(
            '<li><a href="%s" target="_blank" rel="noopener noreferrer">%s</a>%s</li>'
            % (esc(href), _rich(label), note_html)
        )
    if items:
        link_body = '<ul class="ops-links">%s</ul>' % "".join(items)
    else:
        link_body = '<p class="ops-note">No links configured.</p>'
    if steps:
        step_body = "<ol>%s</ol>" % "".join("<li>%s</li>" % _rich(step) for step in steps)
    else:
        step_body = '<p class="ops-note">No steps configured.</p>'
    skills = ", ".join("<code>%s</code>" % esc(name) for name in OPS_SKILLS)
    install = (
        "npm install\n"
        "cp .env.example .env\n"
        "npm run db:reset:local\n"
        "npm run dev"
    )
    return (
        '<section id="view-ops" class="ops" role="tabpanel" aria-labelledby="tab-ops" hidden>'
        "<h2>Important links</h2>"
        "%s"
        "<h2>OpenLocalSEO</h2>"
        "<p>Map-grid rank tracker. A 7×7 grid is fine for now. This product is separate from the seo-skills audit pipeline. Inspired by open-seo; not a fork of its code.</p>"
        "<h3>Install / quick start</h3>"
        '<p>Clone <a href="%s" target="_blank" rel="noopener noreferrer">evankrob/openlocalseo</a>, then:</p>'
        "<pre><code>%s</code></pre>"
        '<p>Opens <a href="%s" target="_blank" rel="noopener noreferrer">%s</a>. Mock data is the default. Cloudflare self-host is a separate section in that README.</p>'
        "<h2>How to run an audit</h2>"
        '<p>From the <a href="%s" target="_blank" rel="noopener noreferrer">seo-skills</a> README, “How to run”.</p>'
        "%s"
        "<h2>On this machine</h2>"
        "<p>Registered Grok Bot skills: %s</p>"
        "</section>"
    ) % (link_body, esc(OPENLOCALSEO_URL), esc(install), esc(LOCAL_APP_URL), esc(LOCAL_APP_URL), esc(SEO_SKILLS_URL), step_body, skills)


def _projects_html(projects: list) -> str:
    panels = []
    nav = [
        '<nav class="proj-nav" role="tablist" aria-label="Own projects">',
        '<p class="proj-kicker">Own projects</p>',
    ]
    for project in projects or []:
        if not isinstance(project, dict):
            continue
        nav.append(_project_nav(project))
        panels.append(_project_panel(project))
    nav.append("</nav>")
    if not panels:
        return (
            '<section id="view-projects" class="projects" role="tabpanel" aria-labelledby="tab-projects" hidden>'
            '<p class="empty-page">No projects in the config.</p>'
            "</section>"
        )
    return (
        '<section id="view-projects" class="projects" role="tabpanel" aria-labelledby="tab-projects" hidden>'
        '<div class="proj-shell">%s<div class="proj-main">%s</div></div>'
        "</section>"
    ) % ("".join(nav), "".join(panels))


def _project_nav(project: dict) -> str:
    project_id = str(project.get("id") or "")
    status = str(project.get("status") or "")
    name = project.get("name") or project_id
    return (
        '<button type="button" class="proj-item" id="proj-tab-%s" data-project-nav="%s" '
        'role="tab" aria-selected="false" aria-controls="project-%s" tabindex="-1">'
        '<span class="dot %s" aria-hidden="true"></span>'
        '<span class="nm">%s</span>'
        '<span class="mini">%s</span>'
        "</button>"
    ) % (
        esc(project_id),
        esc(project_id),
        esc(project_id),
        esc(status),
        esc(name),
        esc(status),
    )


def _project_panel(project: dict) -> str:
    project_id = str(project.get("id") or "")
    status = str(project.get("status") or "")
    updated = str(project.get("updated") or "")
    meta = '<span class="sp %s"><span class="dot" aria-hidden="true"></span>%s</span>' % (
        esc(status),
        esc(status),
    )
    if updated:
        meta += '<time datetime="%s">Updated %s</time>' % (esc(updated), esc(_fmt_iso_day(updated)))
    parts = [
        (
            '<article class="proj-detail" id="project-%s" data-project-panel="%s" '
            'role="tabpanel" aria-labelledby="proj-tab-%s" hidden>'
        )
        % (esc(project_id), esc(project_id), esc(project_id)),
        '<h2 class="proj-title">%s</h2>' % esc(project.get("name") or project_id),
        '<div class="state-card %s">' % esc(status),
        '<p class="eyebrow">Current state</p>',
        '<p class="state">%s</p>' % esc(project.get("state") or ""),
        "</div>",
        '<p class="proj-meta">%s</p>' % meta,
    ]
    links = _project_links(project.get("links") or [])
    if links:
        parts.append("<h3>Links</h3>")
        parts.append(links)
    metrics = _project_metrics(project.get("metrics") or [])
    if metrics:
        parts.append("<h3>Metrics</h3>")
        parts.append(metrics)
    timeline = _project_timeline(project.get("timeline") or [])
    if timeline:
        parts.append("<h3>Recent</h3>")
        parts.append(timeline)
    parts.append("</article>")
    return "".join(parts)


def _project_links(links: list) -> str:
    items = []
    for link in links:
        if not isinstance(link, dict):
            continue
        href = link.get("href") or ""
        if not href:
            continue
        label = link.get("label") or href
        items.append(
            '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
            % (esc(href), esc(label))
        )
    if not items:
        return ""
    return '<div class="proj-links">%s</div>' % "".join(items)


def _project_metrics(metrics: list) -> str:
    cards = []
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        label = metric.get("label") or ""
        value = metric.get("value") or ""
        if not label and not value:
            continue
        cards.append(
            '<div class="metric"><span class="k">%s</span><span class="v">%s</span></div>'
            % (esc(label), esc(value))
        )
    if not cards:
        return ""
    return '<div class="metrics">%s</div>' % "".join(cards)


def _project_timeline(events: list) -> str:
    rows = []
    for event in events:
        if not isinstance(event, dict):
            continue
        what = event.get("what") or ""
        if not what:
            continue
        when = str(event.get("when") or "")
        if when:
            stamp = '<time datetime="%s">%s</time>' % (esc(when), esc(_fmt_iso_day(when)))
        else:
            stamp = "<time></time>"
        rows.append("<li>%s<span class=\"what\">%s</span></li>" % (stamp, esc(what)))
    if not rows:
        return ""
    return '<ol class="timeline">%s</ol>' % "".join(rows)


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _fmt_iso_day(iso: str) -> str:
    parts = str(iso).split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return str(iso)
    year, month, day = (int(part) for part in parts)
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return str(iso)
    return "%s %d, %d" % (_MONTHS[month - 1], day, year)


def _project_pick_css(projects: list) -> str:
    rules = []
    for project in projects or []:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        if not project_id or not _css_id(project_id):
            continue
        rules.append(
            'html[data-project="%s"] [data-project-panel="%s"] { display: block !important; }'
            % (project_id, project_id)
        )
        rules.append(
            'html[data-project="%s"] [data-project-nav="%s"] {'
            " background: var(--nav-on); border-color: var(--line); }"
            % (project_id, project_id)
        )
    return "\n".join(rules)


def _css_id(value: str) -> bool:
    return all(char.isalnum() or char in "_-" for char in value)


def _rich(value: object) -> str:
    """Escape text, and turn paired `backticks` into code."""
    text = "" if value is None else str(value)
    parts = text.split("`")
    if len(parts) == 1 or len(parts) % 2 == 0:
        return esc(text)
    rendered = []
    for index, part in enumerate(parts):
        if index % 2:
            rendered.append("<code>%s</code>" % esc(part))
        else:
            rendered.append(esc(part))
    return "".join(rendered)


def esc(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _subtitle(now: datetime, days: int) -> str:
    start, local_now = window_bounds(now, days)
    zone = local_now.tzname() or ""
    text = "Last %d days · %s – %s" % (days, _fmt_date(start.date()), _fmt_date(local_now.date()))
    if zone:
        text += " · " + zone
    text += " · updated " + _fmt_time(local_now)
    return text


def _fmt_date(day) -> str:
    return "%s %s %d %d" % (day.strftime("%a"), day.strftime("%b"), day.day, day.year)


def _fmt_time(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return "%d:%02d %s" % (hour, dt.minute, suffix)


def _fmt_span(start: datetime, end: datetime) -> str:
    if start.date() != end.date():
        return "→ " + _fmt_time(end)
    left = _fmt_time(start)
    right = _fmt_time(end)
    if left == right:
        return left
    left_hm, left_suffix = left.rsplit(" ", 1)
    right_hm, right_suffix = right.rsplit(" ", 1)
    if left_suffix == right_suffix:
        return "%s–%s %s" % (left_hm, right_hm, left_suffix)
    return "%s–%s" % (left, right)


def _day_heading(day, today) -> str:
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return _fmt_date(day)


def _project_chips(entries: list[dict], preferred: list[str]) -> list[str]:
    present = []
    seen = set()
    for entry in entries:
        project = entry.get("project") or "(unknown)"
        if project not in seen:
            seen.add(project)
            present.append(project)
    ordered = [name for name in preferred if name in seen]
    rest = sorted(name for name in present if name not in ordered)
    return ordered + rest


def _waiting_html(waiting: list[dict], labels: dict | None = None) -> str:
    labels = labels or {}
    items = []
    for entry in waiting:
        project = entry.get("project") or "(unknown)"
        source = labels.get(entry.get("source") or "", entry.get("source") or "")
        bits = ['<li data-project="%s">' % esc(project)]
        bits.append("<b>%s:</b> %s" % (esc(project), esc(entry.get("title") or "")))
        if source:
            bits.append(' <span class="src">%s</span>' % esc(source))
        bits.append("</li>")
        items.append("".join(bits))
    none_hidden = "" if not items else " hidden"
    list_hidden = " hidden" if not items else ""
    return (
        '<section class="wait" aria-label="Waiting on you">'
        "<h2>%s Waiting on you</h2>"
        '<ul%s>%s</ul>'
        '<p class="none"%s>Nothing waiting on you.</p>'
        "</section>"
    ) % (_WAIT_ICON, list_hidden, "".join(items), none_hidden)


def _days_html(entries: list[dict], sources: list[dict], now: datetime) -> str:
    if not sources:
        return ""
    grouped: dict = {}
    for entry in entries:
        end = aware(parse_iso(entry["end"]), now)
        grouped.setdefault(end.date(), []).append((end, entry))
    today = aware(now, now).date()
    html = []
    n = len(sources)
    for day in sorted(grouped, reverse=True):
        html.append('<section class="day">')
        html.append('<h2 class="dayhead">%s</h2>' % esc(_day_heading(day, today)))
        # Literal track lists. repeat(var(--n)) is invalid in some browsers and
        # collapses the grid to a single column.
        html.append('<div class="cols n%d">' % min(n, 6))
        for index, source in enumerate(sources):
            accent = _ACCENTS[index % len(_ACCENTS)]
            items = [pair for pair in grouped[day] if pair[1].get("source") == source["id"]]
            items.sort(key=lambda pair: pair[0], reverse=True)
            html.append(
                '<div class="col %s" data-source="%s" style="--accent:var(--%s)">'
                % (accent, esc(source["id"]), accent)
            )
            html.append("<h3>%s</h3>" % esc(source.get("label") or source["id"]))
            html.append(_groups_html(items, now))
            hidden = "" if not items else " hidden"
            html.append('<p class="empty"%s>Nothing logged.</p>' % hidden)
            html.append("</div>")
        html.append("</div></section>")
    return "".join(html)


def _groups_html(items: list[tuple], now: datetime) -> str:
    if not items:
        return ""
    groups: dict[str, list] = {}
    for end, entry in items:
        groups.setdefault(entry.get("project") or "(unknown)", []).append((end, entry))
    order = sorted(groups, key=lambda name: max(pair[0] for pair in groups[name]), reverse=True)
    html = []
    for project in order:
        html.append('<h4 class="pg" data-project="%s">%s</h4>' % (esc(project), esc(project)))
        for _end, entry in groups[project]:
            html.append(_card(entry, now))
    return "".join(html)


def _card(entry: dict, now: datetime) -> str:
    start = aware(parse_iso(entry["start"]), now)
    end = aware(parse_iso(entry["end"]), now)
    project = entry.get("project") or "(unknown)"
    status = entry.get("status") or ""
    badge = ""
    if status:
        label = _STATUS_LABEL.get(status, status)
        kind = status if status in _STATUS_LABEL else "other"
        badge = '<span class="st %s">%s</span>' % (kind, esc(label))
    meta = _meta(entry)
    files = _files(entry)
    return (
        '<article class="e" data-project="%s">'
        '<time class="t" datetime="%s">%s</time>'
        '<div class="body"><p class="s">%s%s</p>%s%s</div>'
        "</article>"
    ) % (
        esc(project),
        esc(entry.get("end") or ""),
        esc(_fmt_span(start, end)),
        esc(entry.get("title") or ""),
        badge,
        meta,
        files,
    )


def _meta(entry: dict) -> str:
    bits = []
    if entry.get("agent"):
        bits.append(esc(entry["agent"]))
    if entry.get("detail"):
        bits.append(esc(entry["detail"]))
    links = []
    for link in (entry.get("links") or [])[:6]:
        attrs = ' target="_blank" rel="noopener noreferrer"' if link.get("external") else ""
        links.append(
            '<a href="%s"%s>%s</a>' % (esc(link.get("href") or ""), attrs, esc(link.get("label") or "link"))
        )
    text = " · ".join(bits)
    if links:
        text = (text + " " if text else "") + " ".join(links)
    if not text:
        return ""
    return '<p class="m">%s</p>' % text


def _files(entry: dict) -> str:
    files = list(entry.get("files") or [])
    total = int(entry.get("files_total") or len(files))
    linked = {link.get("href") for link in (entry.get("links") or [])}
    linked_count = len([path for path in files if path in linked])
    extra = [path for path in files if path not in linked]
    shown = extra[:FILES_DISPLAY]
    more = max(0, total - linked_count - len(shown))
    if not shown and more <= 0:
        return ""
    label = ", ".join(esc(path) for path in shown)
    if more:
        label = (label + " " if label else "") + "+%d more" % more
    return '<p class="f">%s</p>' % label


_FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
    "%3Crect width='16' height='16' rx='3' fill='%231c1b19'/%3E"
    "%3Crect x='3' y='4' width='4.5' height='8' rx='1' fill='%23e8a27c'/%3E"
    "%3Crect x='8.5' y='4' width='4.5' height='8' rx='1' fill='%238fb0e0'/%3E%3C/svg%3E"
)

_WAIT_ICON = (
    '<svg class="mark" viewBox="0 0 16 16" aria-hidden="true">'
    '<circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-width="1.4"/>'
    '<path d="M8 4.6V8.2l2.3 1.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'
    "</svg>"
)

_HEAD_SCRIPT = """
(function () {
  try {
    var saved = localStorage.getItem("worklog-theme");
    var theme = saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#141412" : "#f3f1eb");
    var view = localStorage.getItem("worklog-view");
    if (view === "ops" || view === "work" || view === "projects") {
      document.documentElement.setAttribute("data-view", view);
    }
    var picked = /^#project=([A-Za-z0-9_-]+)$/.exec(location.hash || "");
    if (picked) {
      document.documentElement.setAttribute("data-view", "projects");
      document.documentElement.setAttribute("data-project", picked[1]);
    }
  } catch (e) {}
})();
""".strip()

_FILTER_SCRIPT = """
(function () {
  var root = document.documentElement;
  var button = document.getElementById("theme");
  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("worklog-theme", theme); } catch (e) {}
    var dark = theme === "dark";
    if (button) {
      button.textContent = dark ? "Light" : "Dark";
      button.setAttribute("aria-pressed", dark ? "true" : "false");
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", dark ? "#141412" : "#f3f1eb");
  }
  applyTheme(root.getAttribute("data-theme") || "light");
  if (button) button.addEventListener("click", function () {
    applyTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
  });

  function applyFilter(name) {
    var all = name === "All";
    document.querySelectorAll(".chip").forEach(function (chip) {
      var on = chip.getAttribute("data-project") === name;
      chip.classList.toggle("on", on);
      chip.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.querySelectorAll(".pg, .e, .wait li").forEach(function (node) {
      node.hidden = !all && node.getAttribute("data-project") !== name;
    });
    var anyDay = false;
    document.querySelectorAll(".day").forEach(function (day) {
      var dayHas = false;
      day.querySelectorAll(".col").forEach(function (col) {
        var visible = col.querySelector(".e:not([hidden])");
        var empty = col.querySelector(".empty");
        if (empty) empty.hidden = !!visible;
        if (visible) dayHas = true;
      });
      day.hidden = !dayHas;
      if (dayHas) anyDay = true;
    });
    var wait = document.querySelector(".wait");
    if (wait) {
      var items = wait.querySelectorAll("li");
      var anyItem = false;
      items.forEach(function (item) { if (!item.hidden) anyItem = true; });
      var list = wait.querySelector("ul");
      var none = wait.querySelector(".none");
      if (list) list.hidden = !anyItem;
      if (none) none.hidden = anyItem;
    }
    var emptyFilter = document.getElementById("empty-filter");
    if (emptyFilter) emptyFilter.hidden = all || anyDay;
  }
  document.querySelectorAll(".chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      applyFilter(chip.getAttribute("data-project") || "All");
    });
  });

  var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-view-tab]"));
  function projectFromHash() {
    var match = /^#project=([A-Za-z0-9_-]+)$/.exec(location.hash || "");
    return match ? match[1] : "";
  }
  function writeProjectHash(id) {
    var next = "#project=" + id;
    if (location.hash === next) return;
    try { history.replaceState(null, "", next); } catch (e) {}
  }
  function clearProjectHash() {
    if ((location.hash || "").indexOf("#project=") !== 0) return;
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
  }
  function applyProject(id) {
    var panels = document.querySelectorAll("[data-project-panel]");
    var buttons = document.querySelectorAll("[data-project-nav]");
    if (!panels.length) return "";
    var known = false;
    panels.forEach(function (panel) {
      if (panel.getAttribute("data-project-panel") === id) known = true;
    });
    if (!known) id = panels[0].getAttribute("data-project-panel");
    root.setAttribute("data-project", id);
    panels.forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-project-panel") !== id;
    });
    buttons.forEach(function (btn) {
      var on = btn.getAttribute("data-project-nav") === id;
      btn.classList.toggle("on", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
      btn.tabIndex = on ? 0 : -1;
    });
    return id;
  }
  function applyView(name) {
    if (name !== "work" && name !== "ops" && name !== "projects") name = "work";
    root.setAttribute("data-view", name);
    try { localStorage.setItem("worklog-view", name); } catch (e) {}
    ["work", "ops", "projects"].forEach(function (id) {
      var panel = document.getElementById("view-" + id);
      if (panel) panel.hidden = id !== name;
    });
    tabs.forEach(function (tab) {
      var on = tab.getAttribute("data-view-tab") === name;
      tab.classList.toggle("on", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    });
    if (name === "projects") {
      var picked = applyProject(projectFromHash() || root.getAttribute("data-project") || "");
      if (picked) writeProjectHash(picked);
      else clearProjectHash();
    } else {
      clearProjectHash();
    }
  }
  var initial = root.getAttribute("data-view");
  if (initial !== "work" && initial !== "ops" && initial !== "projects") initial = "work";
  applyView(initial);
  tabs.forEach(function (tab, index) {
    tab.addEventListener("click", function () {
      applyView(tab.getAttribute("data-view-tab") || "work");
    });
    tab.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      var next = event.key === "ArrowRight" ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length;
      var target = tabs[next];
      applyView(target.getAttribute("data-view-tab") || "work");
      target.focus();
    });
  });
  document.querySelectorAll("[data-project-nav]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = applyProject(btn.getAttribute("data-project-nav") || "");
      if (id) writeProjectHash(id);
    });
    btn.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      event.preventDefault();
      var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-project-nav]"));
      var index = buttons.indexOf(btn);
      var next = event.key === "ArrowDown" ? (index + 1) % buttons.length : (index - 1 + buttons.length) % buttons.length;
      var target = buttons[next];
      var id = applyProject(target.getAttribute("data-project-nav") || "");
      if (id) writeProjectHash(id);
      target.focus();
    });
  });
  window.addEventListener("hashchange", function () {
    var id = projectFromHash();
    if (!id) return;
    applyView("projects");
  });
})();
""".strip()

_CSS = """
:root {
  --bg: #f3f1eb;
  --card: #fffcf7;
  --ink: #1c1b19;
  --muted: #6f6c66;
  --line: #e6e1d6;
  --chip: #fffcf7;
  --chip-line: #d9d3c6;
  --wait-bg: #fff6d8;
  --wait-line: #ead48a;
  --wait-ink: #3f3420;
  --link: #1d4f91;
  --done-bg: #e3f4e6;
  --done-ink: #276b34;
  --waiting-bg: #fdecc8;
  --waiting-ink: #8a5a00;
  --prog-bg: #e1ecfb;
  --prog-ink: #1d4f91;
  --other-bg: #eeeae2;
  --other-ink: #4d4a44;
  --a0: #b4572e;
  --a1: #1d4f91;
  --a2: #0f6e56;
  --a3: #6d4ea3;
  --a4: #8a5a00;
  --a5: #3d5a5b;
  --nav: #f7f4ee;
  --nav-on: #ece6d8;
  --glass: #fffcf7;
  color-scheme: light;
}
html[data-theme="dark"] {
  --bg: #141412;
  --card: #22211e;
  --ink: #f3f0e8;
  --muted: #b1ab9f;
  --line: #34322c;
  --chip: #22211e;
  --chip-line: #3f3c34;
  --wait-bg: #2a2618;
  --wait-line: #6d5b2e;
  --wait-ink: #f3e6c0;
  --link: #9ec0f0;
  --done-bg: #173224;
  --done-ink: #9ed4ae;
  --waiting-bg: #3a2e14;
  --waiting-ink: #f0c36a;
  --prog-bg: #1a2740;
  --prog-ink: #b7d0f7;
  --other-bg: #2c2a26;
  --other-ink: #d9d3c6;
  --a0: #f0a27c;
  --a1: #9ec0f0;
  --a2: #8fd0b8;
  --a3: #d0b6f0;
  --a4: #f0c36a;
  --a5: #b7d0d0;
  --nav: #1a1916;
  --nav-on: #2c2a26;
  --glass: #24231f;
  color-scheme: dark;
}
@media (prefers-color-scheme: dark) {
  html:not([data-theme="light"]) {
    --bg: #141412;
    --card: #22211e;
    --ink: #f3f0e8;
    --muted: #b1ab9f;
    --line: #34322c;
    --chip: #22211e;
    --chip-line: #3f3c34;
    --wait-bg: #2a2618;
    --wait-line: #6d5b2e;
    --wait-ink: #f3e6c0;
    --link: #9ec0f0;
    --done-bg: #173224;
    --done-ink: #9ed4ae;
    --waiting-bg: #3a2e14;
    --waiting-ink: #f0c36a;
    --prog-bg: #1a2740;
    --prog-ink: #b7d0f7;
    --other-bg: #2c2a26;
    --other-ink: #d9d3c6;
    --a0: #f0a27c;
    --a1: #9ec0f0;
    --a2: #8fd0b8;
    --a3: #d0b6f0;
    --a4: #f0c36a;
    --a5: #b7d0d0;
    --nav: #1a1916;
    --nav-on: #2c2a26;
    --glass: #24231f;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html[data-view="ops"] #view-work { display: none !important; }
html[data-view="ops"] #view-ops { display: block !important; }
html[data-view="projects"] #view-work { display: none !important; }
html[data-view="projects"] #view-ops { display: none !important; }
html[data-view="projects"] #view-projects { display: block !important; }
html:not([data-project]) .proj-detail:first-of-type { display: block !important; }
html, body { margin: 0; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  background: var(--bg);
  color: var(--ink);
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px 22px 72px;
  line-height: 1.45;
}
body.wide { max-width: 1280px; }
:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; }
::selection { background: #f0d78a; color: #1c1b19; }
h1 { font-size: 22px; line-height: 1.2; font-weight: 650; letter-spacing: -0.02em; margin: 0; }
.sub { color: var(--muted); font-size: 13px; margin: 4px 0 0; }
.top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
#theme {
  border: 1px solid var(--chip-line);
  background: var(--chip);
  color: var(--ink);
  border-radius: 999px;
  padding: 5px 12px;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.views { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 16px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 16px; }
.chip, .view {
  border: 1px solid var(--chip-line);
  background: var(--chip);
  color: var(--ink);
  border-radius: 999px;
  padding: 5px 12px;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.chip:hover, .view:hover { border-color: var(--ink); }
.chip.on, .view.on { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.ops { max-width: 42rem; }
.ops h2 {
  font-size: 15px;
  font-weight: 650;
  margin: 22px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--line);
}
.ops h2:first-child { margin-top: 2px; }
.ops h3 { margin: 14px 0 6px; font-size: 13px; font-weight: 650; }
.ops p { margin: 0 0 8px; font-size: 14.5px; }
.ops ol { margin: 0 0 8px; padding-left: 1.3rem; }
.ops li { margin: 6px 0; font-size: 14.5px; }
.ops-links { list-style: none; margin: 0; padding: 0; }
.ops-links li {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  margin: 8px 0;
}
.ops-links a { font-weight: 650; }
.ops-note, .ops p.ops-note { color: var(--muted); font-size: 13px; }
.ops-links .ops-note { display: block; margin-top: 3px; }
.ops code, .ops pre {
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 12.5px;
}
.ops code {
  background: var(--other-bg);
  padding: 1px 4px;
  border-radius: 4px;
}
.ops pre {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0 10px;
}
.ops pre code { background: transparent; padding: 0; }
.wait {
  background: var(--wait-bg);
  border: 1px solid var(--wait-line);
  color: var(--wait-ink);
  border-radius: 12px;
  padding: 12px 16px 12px;
  margin: 0 0 8px;
}
.wait h2 {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 650;
  display: flex;
  align-items: center;
  gap: 8px;
  color: inherit;
}
.mark { width: 16px; height: 16px; flex: none; }
.wait ul { margin: 0; padding-left: 18px; }
.wait li { margin: 4px 0; font-size: 14px; }
.wait .src { color: inherit; opacity: 0.7; font-size: 12px; margin-left: 4px; }
.wait .none { margin: 0; font-size: 14px; }
h2.dayhead {
  font-size: 15px;
  font-weight: 650;
  margin: 22px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--line);
}
.cols { display: grid; gap: 16px; align-items: start; }
.n1 { grid-template-columns: minmax(0, 1fr); }
.n2 { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.n3 { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr); }
.n4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.n5, .n6 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.col h3 {
  margin: 2px 0 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent, var(--muted));
}
.pg {
  margin: 12px 0 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
}
.e {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 8px 10px;
  background: var(--card);
  border: 1px solid var(--line);
  border-left: 3px solid var(--accent, var(--line));
  border-radius: 10px;
  padding: 9px 12px;
  margin: 6px 0;
}
.t { color: var(--muted); font-size: 12px; line-height: 1.35; padding-top: 2px; font-variant-numeric: tabular-nums; }
.s { margin: 0; font-size: 14.5px; line-height: 1.35; text-wrap: pretty; }
.m { margin: 4px 0 0; font-size: 12.5px; color: var(--muted); }
.f { margin: 4px 0 0; font-size: 12px; color: var(--muted); word-break: break-word; }
.st {
  display: inline-block;
  font-size: 11px;
  line-height: 1.45;
  padding: 1px 7px;
  border-radius: 999px;
  margin-left: 6px;
  vertical-align: 1px;
  white-space: nowrap;
}
.st.done { background: var(--done-bg); color: var(--done-ink); }
.st.waiting { background: var(--waiting-bg); color: var(--waiting-ink); }
.st.progress { background: var(--prog-bg); color: var(--prog-ink); }
.st.other { background: var(--other-bg); color: var(--other-ink); }
a { color: var(--link); text-underline-offset: 2px; }
.m a { margin-right: 8px; }
.empty, .empty-page { color: var(--muted); font-size: 13px; margin: 4px 0 8px; }
.empty-page { font-size: 15px; margin-top: 12px; }
.projects { background: transparent; border: 0; padding: 0; }
.proj-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.proj-nav {
  background: var(--nav);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 12px 8px;
  position: sticky;
  top: 12px;
}
.proj-kicker {
  margin: 2px 10px 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.proj-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink);
  border-radius: 10px;
  padding: 8px 8px;
  font: inherit;
  font-size: 13.5px;
  cursor: pointer;
}
.proj-item .nm {
  flex: 1;
  min-width: 0;
  font-weight: 620;
  line-height: 1.25;
}
.proj-item .mini {
  color: var(--muted);
  font-size: 11px;
  font-weight: 650;
  flex: none;
}
.proj-item.on,
html:not([data-project]) .proj-nav .proj-item:first-of-type {
  background: var(--nav-on);
  border-color: var(--line);
}
.proj-main { min-width: 0; padding: 6px 8px 10px; }
.proj-title {
  font-size: 34px;
  line-height: 1.08;
  font-weight: 650;
  letter-spacing: -0.035em;
  margin: 0 0 14px;
}
.state-card {
  background: var(--glass);
  border: 1px solid var(--line);
  border-left: 3px solid var(--a2);
  border-radius: 16px;
  padding: 16px 18px;
  margin: 0 0 12px;
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--ink) 5%, transparent);
}
.state-card.waiting { border-left-color: var(--a4); }
.state-card.blocked { border-left-color: var(--a0); }
.state-card.parked { border-left-color: var(--muted); }
.eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.state-card .state {
  margin: 0;
  font-size: 17px;
  line-height: 1.45;
  font-weight: 520;
  text-wrap: pretty;
}
.proj-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 0 0 18px;
  color: var(--muted);
  font-size: 13px;
}
.sp {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.3;
  border-radius: 999px;
  padding: 3px 9px 3px 7px;
  background: var(--other-bg);
  color: var(--other-ink);
}
.sp .dot { width: 7px; height: 7px; background: currentColor; box-shadow: none; }
.sp.active { background: var(--done-bg); color: var(--done-ink); }
.sp.waiting { background: var(--waiting-bg); color: var(--waiting-ink); }
.sp.blocked { background: var(--other-bg); color: var(--a0); }
.sp.parked { background: var(--other-bg); color: var(--muted); }
.dot {
  width: 8px;
  height: 8px;
  border-radius: 99px;
  flex: none;
  background: var(--muted);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--muted) 22%, transparent);
}
.dot.active { background: var(--a2); box-shadow: 0 0 0 3px color-mix(in srgb, var(--a2) 22%, transparent); }
.dot.waiting { background: var(--a4); box-shadow: 0 0 0 3px color-mix(in srgb, var(--a4) 22%, transparent); }
.dot.blocked { background: var(--a0); box-shadow: 0 0 0 3px color-mix(in srgb, var(--a0) 22%, transparent); }
.dot.parked { background: var(--muted); }
.proj-main h3 {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.proj-links { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 18px; }
.proj-links a {
  background: var(--glass);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 6px 12px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 620;
}
.proj-links a::after { content: "↗"; font-size: 11px; margin-left: 6px; color: var(--muted); }
.proj-links a:hover { border-color: var(--ink); }
.metrics { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 18px; }
.metric {
  flex: 1 1 140px;
  max-width: 220px;
  background: var(--glass);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px 14px;
}
.metric .k { display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
.metric .v { font-size: 20px; font-weight: 650; letter-spacing: -0.02em; line-height: 1.2; }
.timeline { list-style: none; margin: 0; padding: 0; }
.timeline li {
  display: grid;
  grid-template-columns: 118px minmax(0, 1fr);
  gap: 12px;
  padding: 8px 0;
  border-top: 1px solid var(--line);
}
.timeline li:first-child { border-top: 0; padding-top: 0; }
.timeline time {
  color: var(--muted);
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
  padding-top: 2px;
}
.timeline time::before {
  content: "";
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 8px;
  border-radius: 99px;
  background: var(--a0);
  vertical-align: 1px;
}
.timeline .what { font-size: 14px; line-height: 1.4; }
@media (max-width: 1100px) {
  .n3, .n4, .n5, .n6 { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
}
@media (max-width: 760px) {
  body { padding: 16px 14px 48px; }
  .top { flex-wrap: wrap; }
  .n1, .n2, .n3, .n4, .n5, .n6 { grid-template-columns: minmax(0, 1fr); }
  .e { grid-template-columns: 76px minmax(0, 1fr); gap: 6px; }
  .proj-shell { grid-template-columns: minmax(0, 1fr); }
  .proj-nav { position: static; }
  .proj-title { font-size: 28px; }
  .timeline li { grid-template-columns: minmax(0, 1fr); gap: 2px; }
}
""".strip()
