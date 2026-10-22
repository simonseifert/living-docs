---
name: docs
description: 'Build and maintain a local, living reference brief for any tool, service, API or SDK in the stack (n8n, Apify, Supabase, Next.js, Stripe, anything). Covers far more than API docs: features, pricing, changelog, status, integrations/actors, gotchas and curated community, plus a sources manifest with per-section freshness. Use it whenever the current task is genuinely about a specific tool: open its brief, refresh it if stale, or build it if missing.'
when_to_use: 'Trigger phrases: "learn <tool>", "research our stack", "know <tool> inside out", "fetch the latest docs for <tool>", "what can <tool> do", "refresh the <tool> brief", "search the docs for", or starting real work against a tool. Never wire it into a session-start hook or global import.'
argument-hint: "<tool> [--deep] | refresh <tool> | search <query> | absorb | --stale | --lint | list | import <tool> <path>"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(${CLAUDE_SKILL_DIR}/scripts/*) Bash(docs-search *)
---

# /docs: living reference briefs for any tool in the stack

Turn any tool, service, API, or SDK into a durable, agent-facing **brief** stored locally, kept fresh on demand. This is the layer Context7 and doc-MCPs do not cover: not just API docs, but features, pricing, changelog, status, available agents/actors, gotchas, and curated public community resources, fused into one file per tool with a machine-readable freshness manifest. The point: when we work with a tool, we know it inside out from a local file, without re-scraping the web every session.

**Library right now:**
!`python3 ${CLAUDE_SKILL_DIR}/scripts/stale.py --summary 2>/dev/null || true`

## Build once, then patch (the foundation model)

A brief is a foundation you build once and maintain, never rebuild from scratch. On any `/docs <tool>`:

1. **Check what exists first.** If `<tool>/` is present, read its `sources.yaml`. If everything is within TTL, just open the brief. Do not re-fetch.
2. **If stale, patch deltas only.** Run `scripts/detect.py <tool>` (free: polls the cheap `change_detector`, such as a GitHub release tag, npm version, RSS date or page hash). For each section whose detector moved OR whose TTL expired, re-fetch only that section, update just those parts of the brief and restamp them. Sections that did not change are left untouched.
3. **Full re-search is per-section, on change.** When a section actually changed, do the deep pass for that section (not the whole tool). The `full/` mirror is incremental too: the KB crawler skips articles it already has.

So the first run is the only expensive one. This is why every stale-able claim maps to a `sources.yaml` entry with a detector.

**Proactive is good; a global hook is not.** Opening or patching a brief because the task is genuinely about tool X is exactly right. The prior implementation died because it fired on every session, including prose and refactors, so never wire this into a session-start hook or an always-loaded import. See `references/design-rationale.md`.

## Usage

```
/docs <tool>                     # build (or open, if fresh) the brief for a tool
/docs <tool> --deep              # build with the --deep extras (see below)
/docs refresh <tool>             # re-fetch only stale or moved sections, restamp
/docs refresh <tool> --section pricing,changelog   # refresh specific sections
/docs refresh <tool> --all       # force full refresh regardless of TTL
/docs search <query> [--tool T]  # full-text search across briefs + full/ dumps (scripts/search.py, also `docs-search`)
/docs absorb                     # work through _inbox/pending.md: facts flagged in your notes for the library
/docs --stale                    # per-section staleness for every brief (scripts/stale.py)
/docs --lint                     # check every sources.yaml parses and has the fields stale.py needs
/docs list                       # list all briefs (INDEX.md)
/docs import <tool> <path>       # adopt an existing hand-written guide as a managed brief (generates its sources.yaml)
```

A bare `/docs <tool>` means: open the brief if it exists and is fresh; otherwise refresh or build it. **Search before you read:** for a specific question ("n8n webhook retry policy"), run `docs-search "<terms>" --tool <tool>` and read only the hits, instead of loading a whole brief or any `full/` file.

**What `--deep` adds over a normal build:** (1) enumerate the full actor/integration/plugin catalog via its API into `full/catalog.json` instead of listing the notable ones; (2) save the complete OpenAPI spec and `llms-full.txt` into `full/`; (3) crawl the whole help center / KB into `full/<kb>/` (normal builds crawl only the sections the brief needs); (4) a wider community sweep: `last30days` plus YouTube channel RSS plus GitHub issues/discussions, not just a WebSearch pass. Use it for tools you work in daily, not for a one-off lookup.

## Where things live

- **This skill** (logic, templates, scripts): `~/.claude/skills/docs/`
- **The reference library** (the data, git-tracked, syncs across machines): `~/docs-reference/`
  - one directory per tool: `docs-reference/<tool>/`
    - `brief.md`: the condensed, agent-facing guide (the thing you read)
    - `sources.yaml`: machine-readable source map + freshness (the thing you refresh from)
    - `full/`: raw dumps for drill-down only (llms-full.txt, openapi.json, actor catalog json). Never loaded wholesale into context.
  - `INDEX.md`: catalog of all briefs with last-verified dates. Keep each row's Notes to one or two sentences (under ~40 words); the long story of a build goes in `<tool>/history.md`, not the index.

Keep the library in a plain directory sub-agents can write (a normal git repo). Avoid note apps or cloud-synced folders that block subprocess writes on macOS; if you want a copy there, mirror it from the main session. Sub-agents never write to a restricted path.

## Non-negotiable rules

1. **Curate, do not dump.** The brief is a hand-quality, opinionated, condensed guide (mental model, recipes, gotchas, pricing, limits). It is NOT a raw docs dump. Store raw dumps in `full/` for drill-down only. (Benchmarks show a condensed guide beats raw-docs-in-a-tool and is ~2.5x cheaper. See `references/design-rationale.md`.)
2. **Lean on what already exists.** For live API/library docs, prefer a first-party MCP if one is connected (Vercel, Supabase, Cloudflare, AWS, Microsoft Learn, Hugging Face, GitHub), then Context7, then the tool's `llms.txt`. Do not re-scrape docs a connected tool already serves. The brief's value-add is everything those do NOT cover.
3. **Secrets are placeholders, always.** Never write a real API key, token, PIT, locationId, or account ID into a brief or `full/`. Use `pit-xxxx`, `<locationId>`, `<api-key>`. The library is git-tracked.
4. **Preserve operator rules.** If the user has a standing rule about a tool (for example "this CRM is manual-only, never let an agent write to a live account"), reproduce it as a prominent callout at the top of that tool's brief. Briefs are reference, not an automation green-light.
5. **Community: scrape what's open, search what's gated (v2).** Actively pull the open public layer, do not just link it: news/blogs (RSS or scrape), the vendor's help center / knowledge base (crawl every article into `full/`, see the KB-crawl recipe in the playbook), changelog feeds, and YouTube (channel RSS). For Reddit and other search-indexed social, use the `last30days` skill, WebSearch, or `reach web <reddit thread URL>` (renders in local Chromium), because raw anonymous Reddit is usually IP-blocked from a datacenter (its `.rss`/`.json` can return a "Blocked" page even on HTTP 200). Only genuinely login-walled content (private Facebook groups, member Slack/Discord history, gated dashboards) is left as `auth-required` in sources.yaml. Never bypass an auth wall.
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

**6. Write `sources.yaml`** using `references/sources-schema.md`: one entry per section under a top-level `sections:` list (not `sources:`), each with `name`, `url`, `method`, `last_fetched`, `ttl_days`, `status` (ok | partial | auth-required | unverified). Quote any value that contains `: ` or starts with a special character. Then run `scripts/stale.py --lint <tool>`; it must report no problems before you commit. Invalid YAML or the wrong key silently breaks staleness checks.

**7. Append to the history log, update `INDEX.md`, commit.** Prepend a dated entry to `<tool>/history.md` (create it on first build) summarizing what this run did: date, versions/prices verified, sections written or changed. Add the same one-liner to the top-level `CHANGELOG.md` under today's date. Then `cd ~/docs-reference && git add <tool> INDEX.md CHANGELOG.md && git commit -m "docs: <build|refresh> <tool>"`. Confirm the commit; do not push unless the user asks.

## Refresh algorithm

Detection is free (pure local Python, no model). Only the actual re-read and patch
spends a model, and that model is a cheap one, never the agent's own tokens.

1. Read the tool's `sources.yaml`. Compute staleness per section (`now - last_fetched` vs `ttl_days`). `scripts/stale.py <tool>` does this. (Free.)
2. Re-fetch only stale sections (or the ones named in `--section`). Cheap first: poll the change_detector (OpenAPI version string, RSS pubDate, GitHub release tag) before re-scraping anything. Fetch with `reach`.
3. **Compare with a cheap model, not the agent.** `scripts/groq_refresh.py --old <section>.md --fetched <slice>.md --section <name> --tool <tool>` sends the current section plus the freshly-fetched source to a cheap OpenAI-compatible model and returns JSON `{changed, summary, updated_section}`. Providers: `groq` (default, `openai/gpt-oss-120b`, free tier, caps request size so send a focused slice), `local` (free `gpt-oss:20b` on your own Ollama, no size cap), `deepseek` (stronger judgment, needs `DEEPSEEK_API_KEY`). Apply `updated_section` only when `changed` is true, and eyeball the diff.
4. Restamp `last_fetched` (and flip `status` to `ok`) for every section you re-verified, including the ones that did not change.
5. **Log the changes.** Prepend a dated entry to `<tool>/history.md` listing exactly what moved (e.g. "pricing Starter $20 -> $24; n8n 2.28 -> 2.29; status/community restamped, no change"). If nothing changed, log "checked, no change". Mirror a one-liner into `CHANGELOG.md`.
6. Commit with `git commit -m "docs: refresh <tool> (<sections>)"`.

### Absorb: facts flagged elsewhere

If other pipelines or your own notes leave lines in a markdown notes folder (`$VAULT_DIR`, default `~/vault`) that mention `docs-reference` or carry an `other:docs-reference` tag. `scripts/inbox.py` (free, runs nightly before the refresh) collects new ones into `<library>/_inbox/pending.md` as a checklist with source path:line, context, URLs and a guessed tool. `/docs absorb` = go through that list: for each item, open the source note, decide if it holds a real, sourced fact for an existing brief (patch that section, add the URL to `sources.yaml`, log it in `history.md`), a reason to build a new brief (note it, ask the user), or nothing (many hits are just mentions of the library path). Delete each item from pending.md once handled. Commit as `docs: absorb <n> items`.

### Nightly auto-refresh (free, local GPU)

`scripts/refresh_batch.py` is meant for a nightly timer (systemd or launchd) on a machine with Ollama. It runs `detect.py`, picks up to 25 sections (tools whose detector moved first, then stale sections of tools used in the last 30 days), fetches each with `reach`, compares with the local model via `groq_refresh.py --provider local`, patches the brief only on a real change, restamps only when the fetched page actually contained the section's facts, logs to `history.md` + `CHANGELOG.md`, commits, unloads the model and sends one ntfy summary. Set `DOCS_GPU_YIELD_TO=<model-prefix>` to make it wait while another resident model on the same GPU was used in the last few minutes. Run log: `<library>/_state/refresh-<date>.json`. To review what it did: `git log --author-date-order -- <tool>/` or `git show` on the `docs: auto-refresh` commits; `git revert` any bad one. A manual `/docs refresh` is still the path for sections it marks `unverified`, `fetch-failed` or `no-heading-match`.

### Weekly freshness ping

`scripts/docs_freshness.py` runs `stale.py` and sends ONE ntfy notification with the most-overdue tools (capped at 12 lines; ntfy turns bodies over 4 KB into attachments). Model-free, zero cost, skips live `status` sections by default. Point it at an ntfy config (see `examples/ntfy.example.json`) via `$DOCS_NTFY_CONFIG` or `~/.config/docs/ntfy.json`, then schedule it weekly with launchd or cron. Refreshing stays a choice: the ping tells you which tool to run `/docs refresh` on.

## Audit trail (what is tracked)

Every brief carries its own paper trail, so you can always answer "where did this come from and is it current":
- **Sources + dates:** `<tool>/sources.yaml` maps each section to its source URL, `method`, `last_fetched`, `ttl_days`, `status`, and a `change_detector`.
- **Change log:** `<tool>/history.md` is an append-only, newest-first log of every build and refresh (date + what changed + versions/prices verified).
- **Library roll-up:** top-level `CHANGELOG.md` aggregates all tools' changes by date.
- **Git history:** each build/refresh is its own commit, so `git log -- <tool>/` and `git diff` show the exact byte-level changes over time.

Default TTLs (override per tool in sources.yaml): status 1d, changelog/news 7d, pricing 30d, actors/integrations 30d, api/docs 30d (or "on-demand" when served live by Context7/MCP), overview/mental-model 180d.

## Composes these installed capabilities

Context7 MCP (live library docs) · first-party MCPs (Vercel/Supabase/Cloudflare/AWS/Microsoft Learn/Hugging Face/GitHub) · **`reach`** (server-less fetch CLI, the primary web backend: `web` = Jina, then a free local Chromium render, then Firecrawl, then curl; `search` = Exa, then SearXNG; `repo-wiki` = DeepWiki, `yt`, `rss`, `repo` = gh, `crawl` = Firecrawl; no MCP servers. Paid backends run out of credits, so run `reach doctor` before a big build and lean on the free tiers) · **`agent-reach`** (only for gated social: Reddit/X/IG/FB via a cookie backend behind a burner profile) · `last30days` / `deep-research` (community sentiment) · `WebSearch`/`WebFetch` · GitHub MCP (releases/issues/discussions). Orchestrate these; do not reimplement them.

## References (load on demand)

- `references/discovery-playbook.md`: per-surface fetch playbook, with Apify + GHL worked examples
- `references/brief-template.md`: the brief skeleton to instantiate
- `references/sources-schema.md`: sources.yaml fields + TTL policy
- `references/example-brief.md`: gold-standard brief to match for depth/tone
- `references/design-rationale.md`: why this design (the prior-art that got deleted, the curate-not-dump evidence, the Context7 gap)
