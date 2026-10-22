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
    detect.py --dry-run          # check everything, do not write _state/detect.json

Fetch tiers (the result notes any tier other than "direct"):
    direct    plain GET (GitHub token only for exact https api.github.com)
    browser   retry after 403/429 with a browser User-Agent + Accept header
    reach     HTML pages still blocked: `reach web <url>` text, hashed
    weak-tls  host offers only weak DH: one retry at SECLEVEL=1, never with auth
Only http(s) urls are fetched; anything else in `urls` is skipped.

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
import ssl
import sys
import json
import hashlib
import datetime
import subprocess
import urllib.error
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
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}
WEAK_TLS_RE = re.compile(r"DH_KEY_TOO_SMALL|dh key too small|EE_KEY_TOO_SMALL|"
                         r"CA_MD_TOO_WEAK|ee key too small|md too weak", re.I)
NON_HTML_RE = re.compile(r"\.(json|xml|atom|rss)(\?|$)|/api/|^https?://api\.|/feed|/rss",
                         re.I)
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


class NotAUrl(Exception):
    """A change_detector entry that is not an http(s) url."""


def is_http(url):
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _open(url, headers, context=None):
    req = urllib.request.Request(url, headers=headers)
    if context is not None:
        # weak-tls path: plain urlopen, no custom handlers, no auth header ever
        resp = urllib.request.urlopen(req, timeout=20, context=context)
    else:
        resp = _OPENER.open(req, timeout=20)
    with resp:
        return resp.read().decode("utf-8", errors="replace")


def _reach_web(url):
    env = dict(os.environ)
    env["PATH"] = str(Path.home() / ".local" / "bin") + os.pathsep + env.get("PATH", "")
    out = subprocess.run(["reach", "web", url], capture_output=True, text=True,
                         timeout=90, env=env)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError("reach web failed: " + (out.stderr.strip()[:120] or "empty output"))
    return out.stdout


def fetch_ex(url):
    """Return (body, tier). Tier is direct, browser, reach or weak-tls."""
    if not is_http(url):
        raise NotAUrl(url)
    headers = {"User-Agent": UA}
    parts = urllib.parse.urlsplit(url)
    # exact host + https only: a substring check would hand the token to
    # e.g. https://api.github.com.evil.example/
    if parts.scheme == "https" and parts.hostname == "api.github.com" and github_token():
        headers["Authorization"] = "Bearer " + github_token()
    try:
        return _open(url, headers), "direct"
    except urllib.error.HTTPError as e:
        if e.code not in (403, 429):
            raise
        blocked = e
    except urllib.error.URLError as e:
        if parts.scheme == "https" and WEAK_TLS_RE.search(str(e)):
            ctx = ssl.create_default_context()
            ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
            return _open(url, dict(BROWSER_HEADERS), ctx), "weak-tls"
        raise
    # blocked: browser headers, never the GitHub token
    try:
        return _open(url, dict(BROWSER_HEADERS)), "browser"
    except urllib.error.HTTPError as e:
        if e.code not in (403, 429):
            raise
        blocked = e
    if NON_HTML_RE.search(url):
        raise blocked
    return _reach_web(url), "reach"


def fetch(url):
    return fetch_ex(url)[0]


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


def detect_url(url, field, tiers=None):
    body, tier = fetch_ex(url)
    if tiers is not None:
        tiers.append(tier)
    return extract(body, field)


def baseline_key(url, keys):
    """Best-effort: the baseline key whose name appears in the url."""
    low = url.lower()
    for k in keys:
        if str(k).lower() in low:
            return k
    return None


def current_values(cd, tiers=None, notes=None):
    """Return a str (single url) or {key: value} (several urls).

    Entries that are not http(s) urls are skipped (noted in `notes`);
    NotAUrl is raised when nothing usable is left.
    """
    urls = cd.get("urls")
    field = cd.get("field")
    if urls:
        last = cd.get("last_value")
        keys = list(last) if isinstance(last, dict) else []
        out = {}
        for u in urls:
            if not is_http(u):
                if notes is not None:
                    notes.append(f"skipped: not a url ({_short(u)})")
                continue
            k = baseline_key(u, keys) or u
            out[k] = detect_url(u, field, tiers)
        if not out:
            raise NotAUrl("no http(s) url in urls")
        return out
    return detect_url(cd["url"], field, tiers)


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
    tiers, notes = [], []
    try:
        cur = current_values(cd, tiers, notes)
    except NotAUrl as e:
        return {"tool": tool, "status": "skipped",
                "reason": f"skipped: not a url ({_short(e)})"}, None
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
    via = sorted(set(tiers) - {"direct"})
    if via:
        res["via"] = via
    if notes:
        res["notes"] = notes
    return res, entry


def all_tools():
    return sorted(p.name for p in LIB.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "_")))


def detect_all(tools=None, save=True):
    """Check tools (default all). Returns {tool: result dict}.

    Updates detect.json unless save=False (dry run)."""
    tools = list(tools) if tools else all_tools()
    state = load_state()
    with ThreadPoolExecutor(max_workers=8) as ex:
        outcomes = list(ex.map(lambda t: check_tool(t, state), tools))
    results = {}
    for tool, (res, entry) in zip(tools, outcomes):
        results[tool] = res
        if entry is not None:
            state[tool] = entry
    if save:
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
    extra = ""
    if res.get("via"):
        extra += "  [" + ",".join(res["via"]) + "]"
    if res.get("notes"):
        extra += "  (" + "; ".join(res["notes"]) + ")"
    if st == "moved":
        return f"{t}: moved  {_short(res['baseline'])} -> {_short(res['value'])}{extra}"
    return f"{t}: same{extra}"


def _short(v):
    s = json.dumps(v) if isinstance(v, dict) else str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def main(argv):
    as_json = "--json" in argv
    only_moved = "--only-moved" in argv
    dry = "--dry-run" in argv
    tools = [a for a in argv if not a.startswith("--")]
    if not LIB.exists():
        print(f"library not found: {LIB}", file=sys.stderr)
        return 1
    results = detect_all(tools or None, save=not dry)
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
