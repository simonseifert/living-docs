#!/usr/bin/env python3
"""Collect facts flagged for the docs-reference library from the Obsidian vault.

Other pipelines leave pointers in ~/vault notes. A line counts only with an
explicit tag (`other:docs-reference`, `#docs-ref`, `#docs-reference`) or when
it mentions docs-reference together with an action word (save, add, put,
store, capture, absorb, file into, update, "-> docs", "for the brief") on the
same or the next line. Bare path mentions do not count. This script scans
~/vault/**/*.md with plain file reads (vault is never modified), and appends
each new hit to <lib>/_inbox/pending.md as a checklist item. `/docs absorb`
works through that file.

Usage:
    inbox.py                # scan, append new items, print counts
    inbox.py --dry-run      # report what would be added, write nothing
    inbox.py --json         # machine-readable list of new items
    inbox.py --prune        # drop pending.md items that fail the rule (keeps seen state)

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
MENTION = re.compile(r"docs-reference", re.I)
TAG = re.compile(r"other:docs-reference|#docs-ref", re.I)
ACTION = re.compile(
    r"\b(save[sd]?|saving|add(s|ed|ing)?|put|store[sd]?|capture[sd]?|absorb(ed|s)?"
    r"|file[sd]? into|update[sd]?)\b|->\s*docs|for the brief|into docs-reference", re.I)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
HEADER = (
    "# Docs inbox\n\n"
    "Facts flagged elsewhere for the library. `/docs absorb` works through "
    "this file; delete items once absorbed or rejected.\n\n"
)


def tool_names():
    return sorted(d.name for d in LIB.iterdir()
                  if d.is_dir() and not d.name.startswith(("_", ".")))


# Never read notes that hold credentials or private records: their context
# lines would be copied into the git-tracked pending.md.
SECRET_NAME = re.compile(r"(api[-_ ]?keys?|secret|password|passwd|credential|token|"
                         r"\.env|keys?\.md$|_sensitive|private)", re.I)
# Redact anything credential-shaped that still slips into a context line.
SECRET_VALUE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w+|"
    r"gsk_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9-]+|"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]*|"
    r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9]))")


def redact(text):
    return SECRET_VALUE.sub("<redacted>", text)


def vault_files():
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not SECRET_NAME.search(d)]
        for f in files:
            if f.endswith(".md") and not SECRET_NAME.search(f):
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


def flagged(line, nxt=""):
    """True for an explicit tag, or docs-reference plus an action word on this/next line."""
    if TAG.search(line):
        return True
    # a mention that is only a backticked path does not count
    if not MENTION.search(re.sub(r"`[^`]*`", " ", line)):
        return False
    if ACTION.search(line):
        return True
    # table rows and folder listings never borrow an action word from the next line
    return not line.lstrip().startswith("|") and bool(ACTION.search(nxt))


def scan(tools):
    items = []
    for p in vault_files():
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = str(p.relative_to(VAULT))
        for i, line in enumerate(lines):
            if not flagged(line, lines[i + 1] if i + 1 < len(lines) else ""):
                continue
            ctx = [redact(l.strip()) for l in lines[i:i + 4]]
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


def prune(pend):
    """Rewrite pending.md keeping only items that pass flagged(); returns (kept, dropped)."""
    text = pend.read_text()
    head, *blocks = re.split(r"(?m)^(?=- \[[ x]\] )", text)
    kept, dropped = [], 0
    for b in blocks:
        m = re.search(r"\| ([^|\n]+?):(\d+)\s*$", b.splitlines()[0])
        ok = True
        if m:
            try:
                lines = (VAULT / m.group(1)).read_text(
                    encoding="utf-8", errors="replace").splitlines()
                i = int(m.group(2)) - 1
                ok = flagged(lines[i], lines[i + 1] if i + 1 < len(lines) else "")
            except (OSError, IndexError):
                ok = True  # source gone: keep, a human decides
        if ok:
            kept.append(b)
        else:
            dropped += 1
    body = head + "".join(kept)
    if dropped:
        today = datetime.date.today().isoformat()
        body = body.rstrip("\n") + (
            f"\n\nPruned {dropped} path-only mentions on {today} "
            "(rule: tag or action word)\n")
        pend.write_text(body)
    return len(kept), dropped


def main():
    ap = argparse.ArgumentParser(description="Collect docs-flagged facts from the vault.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--prune", action="store_true")
    a = ap.parse_args()
    if not VAULT.is_dir():
        sys.exit(f"vault not found: {VAULT}")
    if a.prune:
        pend = LIB / "_inbox" / "pending.md"
        if not pend.exists():
            sys.exit("no pending.md")
        kept, dropped = prune(pend)
        print(f"kept {kept}, pruned {dropped}")
        return
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
