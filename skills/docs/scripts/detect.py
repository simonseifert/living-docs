#!/usr/bin/env python3
"""Cheap change detectors for the docs-reference library (free, no model).

Reads the top-level `change_detector:` block of each tool's sources.yaml,
fetches its url(s), extracts the current value and compares it with the last
known one. Tells you which tools have moved so a refresh can be targeted.

Usage:
    detect.py                    # check every tool
    detect.py n8n zod            # only these tools
    detect.py --json             # machine-readable output
    detect.py --only-moved       # hide same/skipped/error lines

Strategy per url (the `type:` spelling is ignored on purpose):
    JSON body + dotted `field`   -> that field's value
    RSS / Atom body              -> newest pubDate/updated/published (YYYY-MM-DD)
    anything else                -> "sha256:" + hash of tag-stripped, whitespace-collapsed text

State lives in <lib>/_state/detect.json, never in sources.yaml:
    {tool: {value, checked, changed_since, baseline, yaml_last}}
The first run takes sources.yaml `last_value` as the baseline. A tool is
"moved" when the current value differs from the baseline. Hash values whose
baseline is not a "sha256:" value are rebaselined silently (not flagged).

Library root defaults to ~/docs-reference, override with
DOCS_REFERENCE_DIR. Pure stdlib plus PyYAML.
"""
import os
import re
import sys
import json
import hashlib
import datetime
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from pathlib import Path

LIB = Path(os.environ.get(
    "DOCS_REFERENCE_DIR",
    Path.home() / "docs-reference",
))
UA = "docs-detect/1.0"
PATH_RE = re.compile(r"^[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+)*$")
NO_BASELINE = ("", "none", "null", "unfetched", "unknown", "n/a")

_gh_token = None


def _today():
    return datetime.date.today().isoformat()


def state_path():
    return LIB / "_state" / "detect.json"


def load_state():
    try:
        return json.loads(state_path().read_text())
    except Exception:
        return {}


def save_state(state):
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def github_token():
    global _gh_token
    if _gh_token is None:
        try:
            out = subprocess.run(["gh", "auth", "token"], capture_output=True,
                                 text=True, timeout=10)
            _gh_token = out.stdout.strip() if out.returncode == 0 else ""
        except Exception:
            _gh_token = ""
    return _gh_token


class _DropAuthOnHostChange(urllib.request.HTTPRedirectHandler):
    """Never forward the GitHub token to a different host on redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlsplit(newurl).hostname != "api.github.com":
            new.remove_header("Authorization")
        return new


_OPENER = urllib.request.build_opener(_DropAuthOnHostChange)


def fetch(url):
    headers = {"User-Agent": UA}
    parts = urllib.parse.urlsplit(url)
    # exact host + https only: a substring check would hand the token to
    # e.g. https://api.github.com.evil.example/
    if parts.scheme == "https" and parts.hostname == "api.github.com" and github_token():
        headers["Authorization"] = "Bearer " + github_token()
    req = urllib.request.Request(url, headers=headers)
    with _OPENER.open(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def dotted_get(obj, path):
    """Walk a.b.c through dicts (keys may contain hyphens) and list indexes."""
    for key in path.split("."):
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        elif isinstance(obj, list) and key.isdigit() and int(key) < len(obj):
            obj = obj[int(key)]
        else:
            raise KeyError(path)
    return obj


def norm_date(s):
    s = (s or "").strip()
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        pass
    m = re.match(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else s


def newest_feed_date(body):
    """Date of the first item/entry of an RSS or Atom feed, or None."""
    try:
        root = ET.fromstring(body.strip())
    except ET.ParseError:
        return None
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("item", "entry"):
            for child in el:
                ctag = child.tag.rsplit("}", 1)[-1]
                if ctag in ("pubDate", "updated", "published", "date") and child.text:
                    return norm_date(child.text)
            return None
    return None


def text_hash(body):
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", body)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def extract(body, field):
    field = str(field or "").strip()
    try:
        data = json.loads(body)
    except ValueError:
        data = None
    if data is not None and PATH_RE.match(field):
        try:
            return str(dotted_get(data, field)).strip()
        except KeyError:
            pass
    if data is None and body.lstrip().startswith("<"):
        d = newest_feed_date(body)
        if d:
            return d
    return text_hash(body)


def detect_url(url, field):
    return extract(fetch(url), field)


def baseline_key(url, keys):
    """Best-effort: the baseline key whose name appears in the url."""
    low = url.lower()
    for k in keys:
        if str(k).lower() in low:
            return k
    return None


def current_values(cd):
    """Return a str (single url) or {key: value} (several urls)."""
    urls = cd.get("urls")
    field = cd.get("field")
    if urls:
        last = cd.get("last_value")
        keys = list(last) if isinstance(last, dict) else []
        out = {}
        for u in urls:
            k = baseline_key(u, keys) or u
            out[k] = detect_url(u, field)
        return out
    return detect_url(cd["url"], field)


def _s(v):
    return "" if v is None else str(v).strip()


def is_hash(v):
    return _s(v).startswith("sha256:")


def differs(cur, base):
    """True when cur moved away from base. Missing or non-hash baselines are not flagged."""
    cur, base = _s(cur), _s(base)
    if base.lower() in NO_BASELINE:
        return False
    if is_hash(cur) and not is_hash(base):
        return False
    return cur != base


def compare(cur, base):
    """Compare str or dict values; returns (moved, new_baseline_if_silent)."""
    if isinstance(cur, dict):
        bd = base if isinstance(base, dict) else {}
        moved = any(differs(v, bd.get(k)) for k, v in cur.items()) if bd else \
            differs("|".join(f"{k}={v}" for k, v in sorted(cur.items())), base)
        return moved
    return differs(cur, base)


def rebaseline(cur, base):
    """Fill in baseline values that cannot be compared (silent adoption)."""
    if isinstance(cur, dict):
        bd = dict(base) if isinstance(base, dict) else {}
        for k, v in cur.items():
            b = _s(bd.get(k))
            if b.lower() in NO_BASELINE or (is_hash(v) and not is_hash(b)):
                bd[k] = v
        return bd
    b = _s(base)
    if b.lower() in NO_BASELINE or (is_hash(cur) and not is_hash(b)):
        return cur
    return base


def load_detector(tool):
    """Return (change_detector dict or None, reason if unusable)."""
    sp = LIB / tool / "sources.yaml"
    if not sp.exists():
        return None, "no sources.yaml"
    import yaml
    try:
        data = yaml.safe_load(sp.read_text()) or {}
    except Exception as e:
        return None, f"bad yaml: {str(e).splitlines()[0]}"
    cd = data.get("change_detector") if isinstance(data, dict) else None
    if cd is None:
        return None, "no change_detector"
    if isinstance(cd, str):
        return None, "unstructured"
    if not isinstance(cd, dict):
        return None, "unstructured"
    if str(cd.get("type", "")).lower() == "none" or not (cd.get("url") or cd.get("urls")):
        return None, "type none/scrape (no url)"
    return cd, None


def check_tool(tool, state):
    """Return (result dict, new state entry or None)."""
    cd, why = load_detector(tool)
    if cd is None:
        return {"tool": tool, "status": "skipped", "reason": why}, None
    try:
        cur = current_values(cd)
    except Exception as e:
        return {"tool": tool, "status": "error", "reason": f"{type(e).__name__}: {e}"}, None
    prev = state.get(tool) or {}
    yaml_last = cd.get("last_value")
    # a hand-edited last_value in sources.yaml resets the baseline
    if "baseline" in prev and prev.get("yaml_last") == yaml_last:
        base = prev["baseline"]
    else:
        base = yaml_last
        prev = {}
    moved = compare(cur, base)
    base = rebaseline(cur, base)
    today = _today()
    since = (prev.get("changed_since") or today) if moved else None
    entry = {"value": cur, "checked": today, "changed_since": since,
             "baseline": base, "yaml_last": yaml_last}
    res = {"tool": tool, "status": "moved" if moved else "same",
           "value": cur, "baseline": base, "changed_since": since}
    return res, entry


def all_tools():
    return sorted(p.name for p in LIB.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "_")))


def detect_all(tools=None):
    """Check tools (default all). Returns {tool: result dict}; updates detect.json."""
    tools = list(tools) if tools else all_tools()
    state = load_state()
    with ThreadPoolExecutor(max_workers=8) as ex:
        outcomes = list(ex.map(lambda t: check_tool(t, state), tools))
    results = {}
    for tool, (res, entry) in zip(tools, outcomes):
        results[tool] = res
        if entry is not None:
            state[tool] = entry
    save_state(state)
    return results


def accept(tool):
    """Adopt the current value as the baseline (call after a verified refresh)."""
    state = load_state()
    if tool in state:
        state[tool]["baseline"] = state[tool]["value"]
        state[tool]["changed_since"] = None
        save_state(state)


def fmt(res):
    t, st = res["tool"], res["status"]
    if st in ("skipped", "error"):
        return f"{t}: {st}({res['reason']})"
    if st == "moved":
        return f"{t}: moved  {_short(res['baseline'])} -> {_short(res['value'])}"
    return f"{t}: same"


def _short(v):
    s = json.dumps(v) if isinstance(v, dict) else str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def main(argv):
    as_json = "--json" in argv
    only_moved = "--only-moved" in argv
    tools = [a for a in argv if not a.startswith("--")]
    if not LIB.exists():
        print(f"library not found: {LIB}", file=sys.stderr)
        return 1
    results = detect_all(tools or None)
    if only_moved:
        results = {k: v for k, v in results.items() if v["status"] == "moved"}
    if as_json:
        print(json.dumps(results, indent=2))
        return 0
    for res in results.values():
        print(fmt(res))
    if not results:
        print("Nothing moved." if only_moved else "No tools found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
