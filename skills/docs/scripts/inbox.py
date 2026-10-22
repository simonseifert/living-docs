#!/usr/bin/env python3
"""Collect facts flagged for the docs-reference library from the Obsidian vault.

Other pipelines leave pointers in ~/vault notes (lines mentioning
`docs-reference`, `other:docs-reference` or `#docs-ref`). This script scans
~/vault/**/*.md with plain file reads (vault is never modified), and appends
each new hit to <lib>/_inbox/pending.md as a checklist item. `/docs absorb`
works through that file.

Usage:
    inbox.py                # scan, append new items, print counts
    inbox.py --dry-run      # report what would be added, write nothing
    inbox.py --json         # machine-readable list of new items

State: <lib>/_state/inbox-seen.json (hash of file + normalized line), so each
item is reported once. Skips .obsidian and .trash. Env: DOCS_REFERENCE_DIR
(library), VAULT_DIR (default ~/vault).
"""
import os
import re
import sys
import json
import hashlib
import datetime
import argparse
from pathlib import Path

LIB = Path(os.environ.get(
    "DOCS_REFERENCE_DIR",
    Path.home() / "docs-reference",
))
VAULT = Path(os.environ.get("VAULT_DIR", Path.home() / "vault"))
SKIP_DIRS = {".obsidian", ".trash"}
PATTERN = re.compile(r"docs-reference|#docs-ref", re.I)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
HEADER = (
    "# Docs inbox\n\n"
    "Facts flagged elsewhere for the library. `/docs absorb` works through "
    "this file; delete items once absorbed or rejected.\n\n"
)


def tool_names():
    return sorted(d.name for d in LIB.iterdir()
                  if d.is_dir() and not d.name.startswith(("_", ".")))


def vault_files():
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".md"):
                yield Path(root) / f


def item_hash(rel, line):
    norm = re.sub(r"\s+", " ", line.strip().lower())
    return hashlib.sha1(f"{rel}\n{norm}".encode()).hexdigest()


def guess_tool(text, tools):
    low = text.lower()
    for t in tools:
        if re.search(r"(?<![\w.-])" + re.escape(t.lower()) + r"(?![\w-]|\.\w)", low):
            return t
    return "new?"


def scan(tools):
    items = []
    for p in vault_files():
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = str(p.relative_to(VAULT))
        for i, line in enumerate(lines):
            if not PATTERN.search(line):
                continue
            ctx = [l.strip() for l in lines[i:i + 4]]
            block = "\n".join(ctx)
            # a guess from the flagged line wins over the following context
            tool = guess_tool(line, tools)
            if tool == "new?":
                tool = guess_tool(block, tools)
            items.append({
                "hash": item_hash(rel, line),
                "source": rel,
                "line": i + 1,
                "context": [c for c in ctx if c],
                "urls": sorted(set(URL_RE.findall(block))),
                "tool": tool,
            })
    return items


def render(it, today):
    out = [f"- [ ] {today} | tool: {it['tool']} | {it['source']}:{it['line']}"]
    out += [f"  > {c[:300]}" for c in it["context"]]
    if it["urls"]:
        out.append("  urls: " + " ".join(it["urls"]))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Collect docs-flagged facts from the vault.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not VAULT.is_dir():
        sys.exit(f"vault not found: {VAULT}")
    state_f = LIB / "_state" / "inbox-seen.json"
    seen = set()
    if state_f.exists():
        try:
            seen = set(json.loads(state_f.read_text()))
        except ValueError:
            pass
    found = scan(tool_names())
    new, dup = [], set()
    for it in found:
        if it["hash"] in seen or it["hash"] in dup:
            continue
        dup.add(it["hash"])
        new.append(it)
    if not a.dry_run and new:
        today = datetime.date.today().isoformat()
        pend = LIB / "_inbox" / "pending.md"
        pend.parent.mkdir(parents=True, exist_ok=True)
        if not pend.exists():
            pend.write_text(HEADER)
        with pend.open("a") as f:
            f.write("\n".join(render(it, today) for it in new) + "\n")
        state_f.parent.mkdir(parents=True, exist_ok=True)
        state_f.write_text(json.dumps(sorted(seen | dup)))
    if a.json:
        print(json.dumps(new, indent=2))
        return
    by_tool = {}
    for it in new:
        by_tool[it["tool"]] = by_tool.get(it["tool"], 0) + 1
    verb = "would add" if a.dry_run else "added"
    print(f"matched {len(found)} lines, {len(found) - len(new)} already seen/duplicate, "
          f"{verb} {len(new)} new items")
    if by_tool:
        print("by tool: " + ", ".join(f"{k}={v}" for k, v in sorted(by_tool.items())))


if __name__ == "__main__":
    main()
