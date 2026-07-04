---
name: docs
description: Build and maintain a local, living reference brief for ANY tool/service/API/SDK in a project's stack (GHL, n8n, Apify, Supabase, Next.js, Stripe, anything). Fetches far more than API docs: features, pricing/plans, changelog/news, status, available agents/actors/integrations, gotchas, and curated public community resources (docs, forums, Reddit, YouTube, guides), then writes an agent-facing markdown brief plus a machine-readable sources manifest with managed freshness. Use when the user says "learn <tool>", "research our stack", "know <tool> inside out", "fetch the latest docs for <tool>", "build a reference for <tool>", "what can <tool> do", "refresh the <tool> brief", or when starting work with any tool/service in the stack. Invoke it proactively whenever the current task is actually about a specific tool (build or open its brief, or refresh it if stale); the only thing to avoid is wiring it as a global per-session hook.
trigger: /docs
---

# /docs: living reference briefs for any tool in the stack

Turn any tool, service, API, or SDK into a durable, agent-facing **brief** stored locally, kept fresh on demand. This is the layer Context7 and doc-MCPs do not cover: not just API docs, but features, pricing, changelog, status, available agents/actors, gotchas, and curated public community resources, fused into one file per tool with a machine-readable freshness manifest.

**The whole point:** so that when we work with a tool, we know it inside out from a local file, without re-scraping the web every session.

## Build once, then patch (the foundation model)

A brief is a foundation you build once and maintain, never rebuild from scratch. On any `/docs <tool>`:

1. **Check what exists first.** If `<tool>/` is present, read its `sources.yaml`. If everything is within TTL, just open the brief. Do not re-fetch.
2. **If stale, patch deltas only.** Poll the cheap `change_detector`s first (OpenAPI version string, RSS pubDate, GitHub latest-commit). For each section whose detector moved OR whose TTL expired, re-fetch and re-search only that section, then update just those parts of the brief and restamp them. Sections that did not change are left untouched.
3. **Full re-search is per-section, on change.** When a section actually changed, do the deep pass for that section (not the whole tool). The `full/` mirror is incremental too: the KB crawler skips articles it already has and only pulls new/changed ones.

So the first run is the only expensive one. Every run after is: check detectors, patch what moved, keep the foundation. This is why every stale-able claim maps to a `sources.yaml` entry with a detector.

## When to use

Invoke when the user asks to learn, research, or reference a tool in the project's stack, or when starting work with a service the agent does not already know deeply. Trigger phrases: "learn X", "research our stack", "know X inside out", "fetch latest docs for X", "build/refresh a reference for X", "what can X do", "what actors/integrations does X have".

**Proactive is good; a global hook is not.** Use this whenever the user types `/docs`, AND proactively whenever you are about to do real work against a specific tool and no fresh brief exists (thanks to the foundation model, that usually means a cheap "open existing brief" or a small delta refresh, not a full rebuild). The one thing that killed the prior implementation was wiring it as an ALWAYS-ON trigger that fired on every session, including prose and refactors. So the only hard rule is narrow: never wire this into a session-start hook or a global CLAUDE.md import that runs every message. Invoking it because the current task is genuinely about tool X is exactly right. See `references/design-rationale.md`.

## Usage

```
/docs <tool>                     # build (or open, if fresh) the brief for a tool
/docs <tool> --deep              # thorough: enumerate actors/integrations, pull full OpenAPI, wider community sweep
/docs refresh <tool>             # re-fetch only stale sections, restamp
/docs refresh <tool> --section pricing,changelog,status   # refresh specific sections
/docs refresh <tool> --all       # force full refresh regardless of TTL
/docs --stale                    # list every brief with per-section staleness (runs scripts/stale.py)
/docs list                       # list all briefs in the library
/docs import <tool> <path>       # adopt an existing hand-written guide as a managed brief (generates its sources.yaml)
```

If no explicit sub-command is given, treat a bare `/docs <tool>` as: open the brief if it exists and is fresh; otherwise build or refresh it.

## Where things live

- **This skill** (logic, templates, scripts): `~/.claude/skills/docs/`
- **The reference library** (the data, git-tracked, syncs across machines): `~/docs-reference/`
  - one directory per tool: `docs-reference/<tool>/`
    - `brief.md`: the condensed, agent-facing guide (the thing you read)
    - `sources.yaml`: machine-readable source map + freshness (the thing you refresh from)
    - `full/`: raw dumps for drill-down only (llms-full.txt, openapi.json, actor catalog json). Never loaded wholesale into context.
  - `INDEX.md`: catalog of all briefs with last-verified dates

Keep the library in a plain directory sub-agents can write (a normal git repo). Avoid note apps or cloud-synced folders that block subprocess writes on macOS; if you want a copy there, mirror it from the main session. Sub-agents never write to a restricted path.

## Non-negotiable rules

1. **Curate, do not dump.** The brief is a hand-quality, opinionated, condensed guide (mental model, recipes, gotchas, pricing, limits). It is NOT a raw docs dump. Store raw dumps in `full/` for drill-down only. (Benchmarks show a condensed guide beats raw-docs-in-a-tool and is ~2.5x cheaper. See `references/design-rationale.md`.)
2. **Lean on what already exists.** For live API/library docs, prefer a first-party MCP if one is connected (Vercel, Supabase, Cloudflare, AWS, Microsoft Learn, Hugging Face, GitHub), then Context7, then the tool's `llms.txt`. Do not re-scrape docs a connected tool already serves. The brief's value-add is everything those do NOT cover.
3. **Secrets are placeholders, always.** Never write a real API key, token, PIT, locationId, or account ID into a brief or `full/`. Use `pit-xxxx`, `<locationId>`, `<api-key>`. The library is git-tracked.
4. **Preserve operator rules.** If the user has a standing rule about a tool (for example "this CRM is manual-only, never let an agent write to a live account"), reproduce it as a prominent callout at the top of that tool's brief. Briefs are reference, not an automation green-light.
5. **Community: scrape what's open, search what's gated (v2).** Actively pull the open public layer, do not just link it: news/blogs (RSS or scrape), the vendor's help center / knowledge base (crawl every article into `full/`, see the KB-crawl recipe in the playbook), changelog feeds, and YouTube (channel RSS). For Reddit and other search-indexed social, use the `last30days` skill or WebSearch, because raw anonymous Reddit is usually IP-blocked from a datacenter (its `.rss`/`.json` can return a "Blocked" page even on HTTP 200). Only genuinely login-walled content (private Facebook groups, member Slack/Discord history, gated dashboards) is left as `auth-required` in sources.yaml. Never bypass an auth wall.
6. **Every fact gets a source and a date.** Anything in the brief that can go stale (pricing, limits, endpoints, version-specific behavior) maps to an entry in `sources.yaml` with `url` + `last_fetched`. If you cannot source it, mark it `unverified`.

## Build algorithm

Follow `references/discovery-playbook.md` for the full per-surface how-to. Summary:

**1. Identify surfaces.** Determine the tool's canonical domain, docs root, GitHub org/repo (if any), and whether a first-party MCP is connected. Fill in the `sources.yaml` source map first (URLs), then fetch.

**2. Docs layer (prefer live, cheap, structured):**
   - First-party MCP if connected → else Context7 (`resolve-library-id` then `query-docs`) → else the tool's `llms.txt`.
   - Probe, in order: `https://<docs>/llms.txt`, `/docs/llms.txt`, `/llms-full.txt`, `/docs/llms-full.txt`; then the `.md`-suffix trick (append `.md` to any doc URL for clean markdown); then `raw.githubusercontent.com` for GitHub-hosted docs. `scripts/probe_llmstxt.sh <domain>` automates the probe.
   - If none exist and the tool is OSS: GitMCP (swap github.com → gitmcp.io) or Repomix/gitingest for the source. If docs are HTML-only and messy: `firecrawl-scrape` / `firecrawl-download`, or Firecrawl's `/llmstxt` generator to synthesize one.

**3. Product surfaces Context7 misses (this is the differentiator):**
   - **Pricing/plans:** fetch the pricing page (try `pricing.md` first). Record plan tiers, limits, free tier, pass-through/usage costs.
   - **Changelog/news:** prefer an RSS feed (blog RSS, Canny changelog `feed.rss`); else GitHub Releases via the GitHub MCP; else fetch-and-diff the HTML changelog. Record the feed URL.
   - **Status:** record the status-page URL. If it is an Atlassian Statuspage, note `/api/v2/status.json` + `summary.json`. Do not copy a live status into the brief; record how to check it.
   - **Available agents/actors/integrations:** if the tool exposes a catalog API (e.g. Apify `api.apify.com/v2/store` enumerates ~34k actors unauthenticated), record the endpoint and summarize the category taxonomy. Else list the notable integrations from docs.
   - **API contract:** if an OpenAPI spec exists, save it to `full/openapi.json` and record its URL. If it carries a version/timestamp string, record that string as the cheap change-detector.

**4. Community + knowledge-base layer (scrape the open, search the gated):** Crawl the vendor's help center / KB into `full/<kb>/` as markdown (Freshdesk/Zendesk/Intercom all enumerate categories → folders → articles; see the KB-crawl recipe in the playbook). Pull news/blog RSS and the changelog feed. Resolve the YouTube channel RSS. Use `last30days` / `deep-research` / WebSearch for Reddit and social sentiment (raw Reddit is IP-blocked from a datacenter). Save scraped bodies to `full/`, curate a short Community section into the brief, and record each source (with `fetchable`) in sources.yaml. Mark only true auth walls `auth-required`.

**5. Synthesize the brief** using `references/brief-template.md`. Curate hard. Cross-reference the gold-standard example at `references/example-brief.md` for depth and tone (deep feature dives, API auth/limits/endpoints, pitfalls, troubleshooting, a field-experience layer).

**6. Write `sources.yaml`** using `references/sources-schema.md`: one entry per section with `url`, `method`, `last_fetched`, `ttl_days`, `status` (ok | partial | auth-required | unverified).

**7. Append to the history log, update `INDEX.md`, commit.** Prepend a dated entry to `<tool>/history.md` (create it on first build) summarizing what this run did: date, versions/prices verified, sections written or changed. Add the same one-liner to the top-level `CHANGELOG.md` under today's date. Then `cd ~/docs-reference && git add <tool> INDEX.md CHANGELOG.md && git commit -m "docs: <build|refresh> <tool>"`. Confirm the commit; do not push unless the user asks.

## Refresh algorithm

1. Read the tool's `sources.yaml`. Compute staleness per section (`now - last_fetched` vs `ttl_days`). `scripts/stale.py <tool>` does this.
2. Re-fetch only stale sections (or the ones named in `--section`). Cheap first: poll the change_detector (OpenAPI version string, RSS pubDate, GitHub release tag) before re-scraping anything.
3. Update only the changed parts of `brief.md`, restamp `last_fetched`, and record the concrete deltas.
4. **Log the changes.** Prepend a dated entry to `<tool>/history.md` listing exactly what moved (e.g. "pricing Starter $20 -> $24; n8n 2.28 -> 2.29; status/community restamped, no change"). If nothing changed, log "checked, no change". Mirror a one-liner into `CHANGELOG.md`.
5. Commit with `git commit -m "docs: refresh <tool> (<sections>)"`.

## Audit trail (what is tracked)

Every brief carries its own paper trail, so you can always answer "where did this come from and is it current":
- **Sources + dates:** `<tool>/sources.yaml` maps each section to its source URL, `method`, `last_fetched`, `ttl_days`, `status`, and a `change_detector`.
- **Change log:** `<tool>/history.md` is an append-only, newest-first log of every build and refresh (date + what changed + versions/prices verified).
- **Library roll-up:** top-level `CHANGELOG.md` aggregates all tools' changes by date.
- **Git history:** each build/refresh is its own commit, so `git log -- <tool>/` and `git diff` show the exact byte-level changes over time.

Default TTLs (override per tool in sources.yaml): status 1d, changelog/news 7d, pricing 30d, actors/integrations 30d, api/docs 30d (or "on-demand" when served live by Context7/MCP), overview/mental-model 180d.

## Composes these installed capabilities

Context7 MCP (live library docs) · first-party MCPs (Vercel/Supabase/Cloudflare/AWS/Microsoft Learn/Hugging Face/GitHub) · **`reach`** (server-less fetch CLI, the primary web backend: `web` = JS clean-read via Jina, `search` = Exa, `repo-wiki` = DeepWiki, `yt`, `rss`, `repo` = gh, `crawl` = Firecrawl tier-5; no MCP servers, `reach doctor` for status) · **`agent-reach`** (only for gated social: Reddit/X/IG/FB via a cookie backend behind a burner profile) · `last30days` / `deep-research` (community sentiment) · `WebSearch`/`WebFetch` · GitHub MCP (releases/issues/discussions). Orchestrate these; do not reimplement them.

## References (load on demand)

- `references/discovery-playbook.md`: per-surface fetch playbook, with Apify + GHL worked examples
- `references/brief-template.md`: the brief skeleton to instantiate
- `references/sources-schema.md`: sources.yaml fields + TTL policy
- `references/example-brief.md`: gold-standard brief to match for depth/tone
- `references/design-rationale.md`: why this design (the prior-art that got deleted, the curate-not-dump evidence, the Context7 gap)
