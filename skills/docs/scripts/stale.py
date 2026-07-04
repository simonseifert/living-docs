#!/usr/bin/env python3
"""Staleness checker for the docs-reference library.

Reads each tool's sources.yaml and reports per-section staleness
(now - last_fetched vs ttl_days). Powers `/docs --stale`.

Usage:
    stale.py                 # scan the whole library
    stale.py <tool>          # one tool
    stale.py --json          # machine-readable output

Pure stdlib. TTL may be an int (days) or the string "on-demand" (never stale).
Library root defaults to ~/docs-reference, override with
DOCS_REFERENCE_DIR.
"""
import os
import sys
import json
import datetime
from pathlib import Path

LIB = Path(os.environ.get(
    "DOCS_REFERENCE_DIR",
    Path.home() / "docs-reference",
))


def _today():
    # date.today() is allowed here (real script, not a workflow sandbox)
    return datetime.date.today()


def _parse_date(v):
    if isinstance(v, datetime.date):
        return v
    return datetime.date.fromisoformat(str(v).strip())


def load_yaml(path):
    """Minimal YAML loader for the flat sources.yaml shape we emit.

    Prefers PyYAML if available; falls back to a small parser that handles
    the top-level scalars and the `sections:` list of `- key: value` blocks.
    """
    try:
        import yaml  # type: ignore
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        return _fallback_parse(path)


def _val(v):
    """Strip an inline YAML comment (space-#), then surrounding quotes/space.

    Uses " #" (hash preceded by space) as the comment marker so URLs with a
    #fragment survive.
    """
    i = v.find(" #")
    if i != -1:
        v = v[:i]
    return v.strip().strip('"').strip("'")


def _fallback_parse(path):
    data, sections, cur = {}, [], None
    with open(path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            s = line.strip()
            if s.startswith("- "):
                cur = {}
                sections.append(cur)
                s = s[2:].strip()
                if ":" in s:
                    k, _, v = s.partition(":")
                    cur[k.strip()] = _val(v)
                continue
            if ":" in s:
                k, _, v = s.partition(":")
                k, v = k.strip(), _val(v)
                if k == "sections":
                    continue
                if indent >= 2 and cur is not None:
                    cur[k] = v
                else:
                    data[k] = v
    data["sections"] = sections
    return data


def check_tool(tool_dir):
    sp = tool_dir / "sources.yaml"
    if not sp.exists():
        return None
    data = load_yaml(sp) or {}
    rows, today = [], _today()
    for sec in data.get("sections", []) or []:
        name = sec.get("name", "?")
        ttl = sec.get("ttl_days", None)
        status = sec.get("status", "ok")
        lf = sec.get("last_fetched")
        if ttl in ("on-demand", "on_demand", None):
            rows.append((name, status, "on-demand", None, False))
            continue
        try:
            age = (today - _parse_date(lf)).days
            ttl_i = int(ttl)
            rows.append((name, status, f"{age}/{ttl_i}d", age - ttl_i, age > ttl_i))
        except Exception:
            rows.append((name, status, f"?/{ttl}", None, True))
    return {"tool": data.get("tool", tool_dir.name), "rows": rows}


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not LIB.exists():
        print(f"library not found: {LIB}", file=sys.stderr)
        return 1

    if args:
        tool_dirs = [LIB / args[0]]
    else:
        tool_dirs = sorted(p for p in LIB.iterdir()
                           if p.is_dir() and not p.name.startswith((".", "_")))

    results = [r for r in (check_tool(d) for d in tool_dirs) if r]

    if as_json:
        print(json.dumps(results, indent=2))
        return 0

    if not results:
        print("No briefs found. Build one with: /docs <tool>")
        return 0

    any_stale = False
    for r in results:
        stale = [row for row in r["rows"] if row[4]]
        any_stale = any_stale or bool(stale)
        flag = "STALE" if stale else "fresh"
        print(f"\n{r['tool']}  [{flag}]")
        for name, status, age, over, is_stale in r["rows"]:
            mark = "  !" if is_stale else "   "
            extra = "" if status == "ok" else f"  ({status})"
            print(f"{mark} {name:<14} {age:>10}{extra}")
    if not any_stale:
        print("\nAll briefs fresh.")
    else:
        print("\nRefresh stale sections with: /docs refresh <tool>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
