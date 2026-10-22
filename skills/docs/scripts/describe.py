#!/usr/bin/env python3
"""Keep the skill's `when_to_use` line listing the tools that have briefs.

Agents decide whether to load /docs from the skill listing alone. A generic
"use it when the task is about a tool" loses to WebSearch, because the agent
cannot see that a curated brief for *this* tool exists. So the listing names
them. Claude Code truncates description + when_to_use at 1,536 characters, so
tools are ordered by last brief change (most active first) and the tail is cut
with "+N more" when the library outgrows the cap.

Usage:
    describe.py            # rewrite SKILL.md's when_to_use line in place
    describe.py --check    # print the line and its length, change nothing

Library root defaults to ~/docs-reference, override with
DOCS_REFERENCE_DIR. Pure stdlib.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

LIB = Path(os.environ.get(
    "DOCS_REFERENCE_DIR",
    Path.home() / "docs-reference",
))
SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"
CAP = 1536
HEAD = ('Load this skill BEFORE WebSearch/Context7 whenever a question or task involves '
        'a tool with a local brief (fastest: `docs-search "<terms>" --tool <tool>`): ')
TAIL = ('. Also "learn/refresh <tool>" or a new tool worth a brief. No session-start hooks.')


def tools_by_activity():
    tools = [p.name for p in LIB.iterdir()
             if p.is_dir() and not p.name.startswith((".", "_")) and (p / "brief.md").exists()]

    def last_change(t):
        try:
            out = subprocess.run(["git", "-C", str(LIB), "log", "-1", "--format=%ct", "--", t],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
            return int(out or 0)
        except Exception:
            return int((LIB / t / "brief.md").stat().st_mtime)

    return sorted(tools, key=last_change, reverse=True)


def build(description_len):
    tools = tools_by_activity()
    budget = CAP - description_len - len(HEAD) - len(TAIL) - 40  # the listing adds a " - " separator and trims early
    shown = []
    for i, t in enumerate(tools):
        rest = len(tools) - i - 1
        more = f" +{rest} more (see INDEX.md)" if rest else ""
        if len(", ".join(shown + [t])) + len(more) > budget:
            shown.append(f"+{len(tools) - i} more (see INDEX.md)")
            break
        shown.append(t)
    return HEAD + ", ".join(shown) + TAIL


def main(argv):
    text = SKILL.read_text()
    m = re.search(r"^description: '(.*)'$", text, re.M)
    if not m:
        print("SKILL.md: description line not in the expected single-quoted form", file=sys.stderr)
        return 1
    line = build(len(m.group(1)))
    total = len(m.group(1)) + len(line)
    if "--check" in argv:
        print(line)
        print(f"\n{total} / {CAP} chars (description + when_to_use)")
        return 0
    new = re.sub(r"^when_to_use: .*$", "when_to_use: '" + line.replace("'", "''") + "'",
                 text, count=1, flags=re.M)
    if new != text:
        SKILL.write_text(new)
        print(f"when_to_use updated ({total} / {CAP} chars)")
    else:
        print("when_to_use already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
