"""Source adapters. Each one returns redacted summary entries, never transcripts."""

from worklog.sources.claude_code import extract_claude_code
from worklog.sources.claude_desktop import extract_desktop
from worklog.sources.json_log import extract_json

ADAPTERS = {
    "claude-code": extract_claude_code,
    "json": extract_json,
    "claude-desktop": extract_desktop,
}
