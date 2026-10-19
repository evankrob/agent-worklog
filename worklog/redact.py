"""Redact secrets and trim session titles.

Extractors keep a short title, a project name, timestamps, and file paths.
They never write transcript bodies. Anything that looks like a credential is
replaced before it can land in the log or the page.
"""

from __future__ import annotations

import re

TITLE_MAX = 100

# Order matters only when patterns overlap. Each replacement is "[redacted]".
# These are defensive filters, not a complete secret detector.
SECRET_PATTERNS = [
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----|$)",
    r"\b(sk|pk|rk)[-_](live|test|ant|proj)?[-_]?[A-Za-z0-9_\-]{12,}",
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bAIza[0-9A-Za-z_\-]{30,}",
    r"\bya29\.[0-9A-Za-z_\-]+",
    r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}",
    r"(?i)\bbearer\s+[A-Za-z0-9._\-]{12,}",
    r"(?i)\b(password|passwd|pwd|passcode|secret|token|api[_ -]?key|apikey|auth|credential)s?\b\s*(is\s+)?[:=]\s*\S+",
    r"(?i)\b(password|passwd|pwd|passcode|secret|token|api[_ -]?key|apikey|credential)s?\b\s+(is\s+)?(?=\S*\d)(?=\S*[A-Za-z])\S{6,}",
    r"https?://[^\s/:@]+:[^\s/@]+@",
    r"\b[A-Fa-f0-9]{32,}\b",
    r"\b[A-Za-z0-9+/_\-]{40,}={0,2}",
]

SECRET_RE = [re.compile(p) for p in SECRET_PATTERNS]

_PAIRED_TAGS = re.compile(r"<[^>]+>[\s\S]*?</[^>]+>")
_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def redact(text: str) -> str:
    """Replace secret-shaped substrings. Non-strings are returned unchanged."""
    if not isinstance(text, str) or not text:
        return text
    out = text
    for pattern in SECRET_RE:
        out = pattern.sub("[redacted]", out)
    return out


def title_from(text: str) -> str:
    """A single-line title of at most 100 characters, with secrets removed.

    Tagged blocks (Claude's command and system wrappers) are dropped before
    the limit is applied, so the title is the human's words.
    """
    if not text:
        return ""
    cleaned = _PAIRED_TAGS.sub(" ", text)
    cleaned = _TAGS.sub(" ", cleaned)
    cleaned = _SPACE.sub(" ", cleaned).strip()
    cleaned = redact(cleaned)
    if len(cleaned) > TITLE_MAX:
        return cleaned[: TITLE_MAX - 3] + "..."
    return cleaned


def compile_excludes(patterns: list[str]) -> list[re.Pattern[str]]:
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            raise ValueError("invalid exclude pattern %r: %s" % (pattern, exc)) from exc
    return compiled


def is_excluded(patterns: list[re.Pattern[str]], blobs: list[str | None]) -> bool:
    """True when any blob matches any exclude pattern."""
    for blob in blobs:
        if not blob:
            continue
        for pattern in patterns:
            if pattern.search(blob):
                return True
    return False
