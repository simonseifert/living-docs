#!/usr/bin/env python3
"""Score the library against a ground-truth question set. Free, no model.

Each question in <lib>/_eval/questions.yaml carries a live-verified answer and
1-3 distinctive strings a correct passage must contain (`expect_any`). Two
scores per question:

  found   the top search hits (what an agent actually reads) contain an
          expected string: search + brief together work;
  correct the brief contains an expected string anywhere: the brief holds the
          true current fact (if not, the brief is wrong or missing it).

A question whose `verified` date is older than --max-age days is reported as
due for re-verification instead of trusted: ground truth goes stale too.

Usage:
    eval.py                 # table + summary, exit 1 if anything fails
    eval.py --json          # machine-readable
    eval.py --summary       # one line (used by the nightly ntfy summary)
    eval.py --max-age 60    # ground truth older than this many days = due

Library root defaults to ~/docs-reference, override with
DOCS_REFERENCE_DIR. Needs PyYAML.
"""
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

LIB = Path(os.environ.get(
    "DOCS_REFERENCE_DIR",
    Path.home() / "docs-reference",
))
SEARCH = Path(__file__).resolve().parent / "search.py"
QUESTIONS = LIB / "_eval" / "questions.yaml"


def hits_for(question, tool, k=5):
    out = subprocess.run([sys.executable, str(SEARCH), question, "--tool", tool, "--limit", str(k),
                          "--json", "--full"], capture_output=True, text=True, timeout=60)
    try:
        return json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return []


def contains(text, needles):
    low = (text or "").lower()
    return any(n.lower() in low for n in needles)


def score(q, max_age):
    tool, needles = q["tool"], q.get("expect_any") or []
    brief = LIB / tool / "brief.md"
    hits = hits_for(q["question"], tool)
    found = any(contains(h.get("text") or h.get("snippet"), needles) for h in hits)
    correct = brief.exists() and contains(brief.read_text(errors="replace"), needles)
    try:
        age = (datetime.date.today() - datetime.date.fromisoformat(str(q.get("verified")))).days
    except ValueError:
        age = 10**6
    return {"id": q["id"], "tool": tool, "kind": q.get("kind", ""), "found": found,
            "correct": correct, "due": age > max_age, "answer": q.get("answer", "")}


def main(argv):
    max_age = 60
    if "--max-age" in argv:
        max_age = int(argv[argv.index("--max-age") + 1])
    if not QUESTIONS.exists():
        print(f"no question set at {QUESTIONS}", file=sys.stderr)
        return 1
    qs = yaml.safe_load(QUESTIONS.read_text()) or []
    rows = [score(q, max_age) for q in qs]
    n = len(rows)
    found = sum(r["found"] for r in rows)
    correct = sum(r["correct"] for r in rows)
    due = sum(r["due"] for r in rows)
    line = (f"eval: {found}/{n} answerable from search, {correct}/{n} briefs hold the true fact"
            + (f", {due} question(s) due for re-verification" if due else ""))
    if "--json" in argv:
        print(json.dumps({"found": found, "correct": correct, "n": n, "due": due, "rows": rows}, indent=2))
    elif "--summary" in argv:
        print(line)
    else:
        print(f"{'id':32} {'kind':8} found correct")
        for r in rows:
            flag = "" if r["found"] and r["correct"] else "   <-- " + (
                "brief is wrong or missing: " + r["answer"][:60] if not r["correct"] else "search misses it")
            print(f"{r['id'][:32]:32} {r['kind'][:8]:8} {'y' if r['found'] else 'n':5} "
                  f"{'y' if r['correct'] else 'n':7}{' (due)' if r['due'] else ''}{flag}")
        print("\n" + line)
    return 0 if found == n and correct == n else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
