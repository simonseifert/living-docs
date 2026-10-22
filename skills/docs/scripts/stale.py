#!/usr/bin/env python3
"""Staleness checker for the docs-reference library.

Reads each tool's sources.yaml and reports per-section staleness
(now - last_fetched vs ttl_days). Powers `/docs --stale`.

Usage:
    stale.py                 # scan the whole library
    stale.py <tool>          # one tool
    stale.py --json          # machine-readable output
    stale.py --lint          # check every sources.yaml parses and has the fields stale.py needs
    stale.py --summary       # one short paragraph (injected into SKILL.md when /docs loads)

Pure stdlib (uses PyYAML when installed). TTL may be an int (days) or the
string "on-demand" (never stale). Accepts the section list under `sections:`
or the older `sources:` key, as a list of `- name: ...` blocks or a mapping
keyed by section name.
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


def load_yaml(path, errors=None):
    """Load a sources.yaml.

    Prefers PyYAML if available; falls back to a small parser that handles
    the top-level scalars and the `sections:` list of `- key: value` blocks.
    A file PyYAML rejects is still read via the fallback, but the error is
    recorded in `errors` so --lint can surface it instead of hiding it.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        return _fallback_parse(path)
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        if errors is not None:
            errors.append(f"invalid YAML: {str(e).splitlines()[0]} "
                          f"({' '.join(str(e).split()[-4:])})")
        return _fallback_parse(path)


def get_sections(data):
    """Normalize the section list to a list of dicts with a `name`."""
    if not isinstance(data, dict):
        return []
    secs = data.get("sections")
    if not secs:
        secs = data.get("sources")
    if isinstance(secs, dict):
        out = []
        for k, v in secs.items():
            if isinstance(v, dict):
                v = dict(v)
                v.setdefault("name", k)
                out.append(v)
        return out
    if isinstance(secs, list):
        return [x for x in secs if isinstance(x, dict)]
    return []


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
                if k in ("sections", "sources"):
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
    for sec in get_sections(data):
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
    tool = data.get("tool", tool_dir.name) if isinstance(data, dict) else tool_dir.name
    return {"tool": tool, "rows": rows}


def summary(tool_dirs):
    """Print a 2-3 line library status. Live status sections are ignored."""
    results = [r for r in (check_tool(d) for d in tool_dirs) if r]
    worst, n_stale = [], 0
    for r in results:
        rows = [row for row in r["rows"] if row[4] and "status" not in row[0].lower()]
        if not rows:
            continue
        n_stale += len(rows)
        over = max((row[3] if row[3] is not None else 10**6) for row in rows)
        worst.append((over, r["tool"]))
    worst.sort(reverse=True)
    tools_stale = len(worst)
    print(f"Library: {len(results)} briefs at {LIB}; {tools_stale} have stale content "
          f"sections ({n_stale} total).")
    if worst:
        top = ", ".join(f"{t} ({'never fetched' if o >= 10**6 else f'{o}d over'})"
                        for o, t in worst[:5])
        print(f"Most overdue: {top}.")
    state = LIB / "_state"
    runs = sorted(state.glob("refresh-*.json")) if state.exists() else []
    if runs:
        try:
            last = json.loads(runs[-1].read_text())
            print(f"Last auto-refresh: {runs[-1].stem[8:]} "
                  f"({last.get('checked', '?')} checked, {last.get('changed', '?')} changed).")
        except Exception:
            pass
    return 0


def lint(tool_dirs):
    """Report manifests stale.py cannot fully trust. Exit 1 if any problem."""
    problems = 0
    for d in tool_dirs:
        sp = d / "sources.yaml"
        if not sp.exists():
            print(f"{d.name}: no sources.yaml (brief can never go stale)")
            problems += 1
            continue
        errs = []
        data = load_yaml(sp, errs) or {}
        secs = get_sections(data)
        if not secs:
            errs.append("no sections found (expected `sections:` list)")
        elif isinstance(data, dict) and "sections" not in data:
            errs.append("uses old `sources:` key, rename to `sections:`")
        for sec in secs:
            missing = [k for k in ("name", "url", "last_fetched", "ttl_days") if k not in sec]
            if missing:
                errs.append(f"section {sec.get('name', '?')}: missing {', '.join(missing)}")
                continue
            if sec["last_fetched"] in (None, ""):
                errs.append(f"section {sec['name']}: never fetched (counts as stale)")
            elif str(sec["ttl_days"]) not in ("on-demand", "on_demand"):
                try:
                    _parse_date(sec["last_fetched"])
                    int(sec["ttl_days"])
                except Exception:
                    errs.append(f"section {sec['name']}: bad last_fetched/ttl_days")
        for e in errs:
            print(f"{d.name}: {e}")
        problems += bool(errs)
    print(f"\n{problems} of {len(tool_dirs)} manifests need attention." if problems
          else f"All {len(tool_dirs)} manifests OK.")
    return 1 if problems else 0


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

    if "--lint" in argv:
        return lint(tool_dirs)

    if "--summary" in argv:
        return summary(tool_dirs)

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
