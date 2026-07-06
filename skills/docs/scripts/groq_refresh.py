#!/usr/bin/env python3
"""groq_refresh.py: the cheap-model refresh brain for /docs.

Given a brief section's CURRENT text and a freshly-fetched SOURCE, ask an
OpenAI-compatible cheap model (Groq by default, DeepSeek-compatible) whether the
facts changed, and if so return a corrected version of the section. This is what
keeps /docs refresh off the Claude bill: detection is free (stale.py), and the
re-read/patch runs here on Groq, not Claude.

Usage:
    groq_refresh.py --old OLD.md --fetched FETCHED.md --section pricing [--tool ghl]
    # prints JSON: {"changed": bool, "summary": "...", "updated_section": "..."|null}

Provider (OpenAI-compatible, pick with --provider):
    groq      [default]  openai/gpt-oss-120b @ api.groq.com  (fast, free-tier, key=GROQ_API_KEY)
    deepseek             deepseek-chat @ api.deepseek.com     (stronger, bigger inputs, key=DEEPSEEK_API_KEY)
    --model / --base override either. Keys are read from env or ~/.reach/keys.env.

Why Groq is the default: for this light task (compare a section to a fetched
public page, emit a JSON verdict) gpt-oss-120b is accurate enough, much faster,
already configured, and free. Switch to --provider deepseek when you want stronger
judgment on ambiguous facts or need to send a bigger source (Groq caps request size).

Pure stdlib. No secrets are ever printed.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KEYS = os.environ.get("REACH_KEYS", str(Path.home() / ".reach" / "keys.env"))

# OpenAI-compatible providers. Groq default: fast, free-tier, already configured.
# DeepSeek: stronger judgment + bigger inputs, needs its own key.
PROVIDERS = {
    "groq":     {"base": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b", "key_env": "GROQ_API_KEY"},
    "deepseek": {"base": "https://api.deepseek.com/v1",    "model": "deepseek-chat",       "key_env": "DEEPSEEK_API_KEY"},
}


def load_key(var):
    if os.environ.get(var):
        return os.environ[var]
    p = Path(KEYS)
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line.startswith(var) and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


SYSTEM = (
    "You maintain a factual reference brief. You are given the CURRENT section of "
    "the brief and a freshly-fetched SOURCE for the same topic. Your job: decide "
    "whether any FACT in the current section is now wrong or outdated versus the "
    "source (prices, versions, limits, dates, plan names, endpoints). "
    "Rules: only change facts the source actually contradicts or adds; keep the "
    "same markdown structure, tone, and ordering; keep any placeholder secrets as "
    "placeholders; never invent numbers not present in the source; do NOT use em "
    "dashes (use '-' or ':'); if the source is a nav shell / blocked / lacks the "
    "facts, treat as unchanged. "
    'Respond with ONLY a JSON object: {"changed": bool, "summary": "<=15 words", '
    '"updated_section": "<full corrected markdown, or null if unchanged>"}.'
)


def call(base, model, key, old, fetched, section, tool, max_chars):
    user = (
        f"TOOL: {tool}\nSECTION: {section}\n\n"
        f"=== CURRENT SECTION ===\n{old}\n\n"
        f"=== FRESHLY FETCHED SOURCE (may be noisy) ===\n{fetched[:max_chars]}\n"
    )
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # Groq sits behind Cloudflare, which 403s the default Python-urllib UA
            "User-Agent": "reach-docs-refresh/1.0",
        },
    )
    # honor 429 Retry-After for unattended runs; back off on transient 5xx
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
            content = data["choices"][0]["message"]["content"]
            return content, data.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 3:
                ra = e.headers.get("Retry-After")
                wait = float(ra) if (ra and ra.replace(".", "", 1).isdigit()) else (5 * (attempt + 1))
                time.sleep(min(wait, 30))
                continue
            raise
    raise RuntimeError("unreachable")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--fetched", required=True)
    ap.add_argument("--section", required=True)
    ap.add_argument("--tool", default="")
    ap.add_argument("--provider", default="groq", choices=list(PROVIDERS))
    ap.add_argument("--model", default=None, help="override the provider's default model")
    ap.add_argument("--base", default=None, help="override the provider's default base URL")
    ap.add_argument("--max-chars", type=int, default=11000,
                    help="cap on fetched-source chars sent (Groq caps request size)")
    a = ap.parse_args(argv)

    prov = PROVIDERS[a.provider]
    base = a.base or prov["base"]
    model = a.model or prov["model"]
    key = load_key(prov["key_env"])
    if not key:
        print(json.dumps({"error": f"no {prov['key_env']} in env or {KEYS}"}), file=sys.stderr)
        return 3

    old = Path(a.old).read_text()
    fetched = Path(a.fetched).read_text()
    try:
        content, usage = call(base, model, key, old, fetched, a.section, a.tool, a.max_chars)
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 1

    # validate JSON; pass through verbatim on success
    try:
        obj = json.loads(content)
    except Exception:
        print(json.dumps({"error": "model did not return valid JSON", "raw": content[:500]}), file=sys.stderr)
        return 2
    obj["_usage"] = usage
    obj["_provider"] = a.provider
    obj["_model"] = model
    print(json.dumps(obj, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
