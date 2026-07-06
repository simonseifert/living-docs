#!/usr/bin/env python3
"""docs_freshness.py: weekly staleness ping for the docs-reference library.

Runs stale.py (free, local, no model), collects the sections past their TTL,
and sends ONE ntfy notification listing them. Detection costs nothing: no Claude,
no Groq. You only get pinged when something is actually stale, and then you decide
whether to run `/docs refresh <tool>` (which uses the cheap Groq path).

Sends via ntfy (https://ntfy.sh or self-hosted). Point it at a small JSON config:
    {"ntfy": {"server": "https://ntfy.sh", "topic": "<your-topic>", "auth_token": ""}}
Looked up in order: $DOCS_NTFY_CONFIG, ~/.config/docs/ntfy.json, ~/.reach/ntfy.json.
If no config is found it just prints the stale list instead of pushing. No secrets
are printed.

Usage:
    docs_freshness.py            # ping if content is stale, else stay silent
    docs_freshness.py --dry-run  # print what it would send, do not POST
    docs_freshness.py --always   # ping even when everything is fresh
    docs_freshness.py --include-status  # also count live status-page sections

Live status pages (ttl_days: 1) are checked on demand, not cached in the brief,
so they are excluded by default: otherwise every tool flags daily and the ping is
noise. The weekly ping is about content drift (pricing, changelogs, versions).

Env:
    DOCS_REFERENCE_DIR  library root (default ~/docs-reference; stale.py honors it)
    DOCS_NTFY_CONFIG    path to a JSON file with an {"ntfy": {...}} block
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
STALE = SKILL_DIR / "stale.py"


def _resolve_ntfy_config():
    env = os.environ.get("DOCS_NTFY_CONFIG")
    if env:
        return Path(env)
    for c in (Path.home() / ".config" / "docs" / "ntfy.json",
              Path.home() / ".reach" / "ntfy.json"):
        if c.exists():
            return c
    return Path.home() / ".config" / "docs" / "ntfy.json"  # default; may not exist (graceful)


NTFY_CONFIG = _resolve_ntfy_config()


def _is_status_section(name):
    return "status" in name.lower()


def get_stale(include_status=False):
    out = subprocess.run(
        [sys.executable, str(STALE), "--json"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        print("stale.py failed:", out.stderr.strip(), file=sys.stderr)
        return None
    data = json.loads(out.stdout)
    stale = []
    for r in data:
        for name, status, age, over, is_stale in r["rows"]:
            if not is_stale:
                continue
            if not include_status and _is_status_section(name):
                continue
            stale.append((r["tool"], name, age, status))
    return stale


def load_ntfy():
    if not NTFY_CONFIG.exists():
        return None
    cfg = json.loads(NTFY_CONFIG.read_text())
    n = cfg.get("ntfy")
    if not n or not n.get("server") or not n.get("topic"):
        return None
    return n


def send(ntfy, title, body, priority):
    url = ntfy["server"].rstrip("/") + "/" + ntfy["topic"]
    headers = {
        "Title": title,
        "Priority": str(priority),
        "Tags": "books",
        "User-Agent": "docs-freshness/1.0",
    }
    token = ntfy.get("auth_token") or ""
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=body.encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status


def main(argv):
    dry = "--dry-run" in argv
    always = "--always" in argv
    include_status = "--include-status" in argv

    stale = get_stale(include_status=include_status)
    if stale is None:
        return 1

    if not stale and not always:
        print("all briefs fresh, nothing to send")
        return 0

    # group by tool
    by_tool = {}
    for tool, name, age, status in stale:
        by_tool.setdefault(tool, []).append(f"{name} ({age})")

    if stale:
        title = f"docs: {len(stale)} stale section(s) in {len(by_tool)} tool(s)"
        lines = [f"- {t}: {', '.join(s)}" for t, s in sorted(by_tool.items())]
        body = "\n".join(lines) + "\n\nRefresh with /docs refresh <tool>"
        priority = 3
    else:
        title = "docs: all briefs fresh"
        body = "No stale sections. Library is current."
        priority = 2

    print(title)
    print(body)

    if dry:
        print("\n[dry-run] not sending")
        return 0

    ntfy = load_ntfy()
    if not ntfy:
        print(f"\nno usable ntfy config at {NTFY_CONFIG}; printed above instead", file=sys.stderr)
        return 0
    try:
        code = send(ntfy, title, body, priority)
        print(f"\nntfy sent (HTTP {code}) to topic {ntfy['topic'][:3]}***")
    except Exception as e:
        print(f"\nntfy send failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
