# Building a brief

Loaded by `/docs <tool>` when the brief does not exist yet, and by `/docs <tool> --deep`.

## Build once, then patch

A brief is a foundation you build once and maintain, never rebuild from scratch. On any `/docs <tool>`:

1. **Check what exists first.** If `<tool>/` is present, read its `sources.yaml`. If everything is within TTL, just open the brief. Do not re-fetch.
2. **If stale, patch deltas only.** Run `scripts/detect.py <tool>` (free: polls the cheap `change_detector`, such as a GitHub release tag, npm version, RSS date or page hash). For each section whose detector moved OR whose TTL expired, re-fetch only that section, update just those parts of the brief and restamp them. Sections that did not change are left untouched.
3. **Full re-search is per-section, on change.** When a section actually changed, do the deep pass for that section (not the whole tool). The `full/` mirror is incremental too: the KB crawler skips articles it already has.

So the first run is the only expensive one. This is why every stale-able claim maps to a `sources.yaml` entry with a detector.

## Build steps

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

**7. Append to the history log, update `INDEX.md`, commit.** Prepend a dated entry to `<tool>/history.md` (create it on first build) summarizing what this run did: date, versions/prices verified, sections written or changed. Add the same one-liner to the top-level `CHANGELOG.md` under today's date. Then `cd ~/docs-reference && git add <tool> INDEX.md CHANGELOG.md && git commit -m "docs: <build|refresh> <tool>"`. Confirm the commit; do not push unless the user asks. For a NEW tool, also run `scripts/describe.py` so the skill listing names it (agents only reach for /docs when they can see a brief exists; the nightly job does this too).

## Community layer rule

**Community: scrape what's open, search what's gated (v2).** Actively pull the open public layer, do not just link it: news/blogs (RSS or scrape), the vendor's help center / knowledge base (crawl every article into `full/`, see the KB-crawl recipe in the playbook), changelog feeds, and YouTube (channel RSS). For Reddit and other search-indexed social, use the `last30days` skill, WebSearch, or `reach web <reddit thread URL>` (renders in local Chromium), because raw anonymous Reddit is usually IP-blocked from a datacenter (its `.rss`/`.json` can return a "Blocked" page even on HTTP 200). Only genuinely login-walled content (private Facebook groups, member Slack/Discord history, gated dashboards) is left as `auth-required` in sources.yaml. Never bypass an auth wall.

## What `--deep` adds

Over a normal build: (1) enumerate the full actor/integration/plugin catalog via its API into `full/catalog.json` instead of listing the notable ones; (2) save the complete OpenAPI spec and `llms-full.txt` into `full/`; (3) crawl the whole help center / KB into `full/<kb>/` (normal builds crawl only the sections the brief needs); (4) a wider community sweep: `last30days` plus YouTube channel RSS plus GitHub issues/discussions, not just a WebSearch pass. Use it for tools you work in daily, not for a one-off lookup.

## Audit trail (what is tracked)

Every brief carries its own paper trail, so you can always answer "where did this come from and is it current":
- **Sources + dates:** `<tool>/sources.yaml` maps each section to its source URL, `method`, `last_fetched`, `ttl_days`, `status`, and a `change_detector`.
- **Change log:** `<tool>/history.md` is an append-only, newest-first log of every build and refresh (date + what changed + versions/prices verified).
- **Library roll-up:** top-level `CHANGELOG.md` aggregates all tools' changes by date.
- **Git history:** each build/refresh is its own commit, so `git log -- <tool>/` and `git diff` show the exact byte-level changes over time.

Default TTLs (override per tool in sources.yaml): status 1d, changelog/news 7d, pricing 30d, actors/integrations 30d, api/docs 30d (or "on-demand" when served live by Context7/MCP), overview/mental-model 180d.

## Composes these installed capabilities

Context7 MCP (live library docs) · first-party MCPs (Vercel/Supabase/Cloudflare/AWS/Microsoft Learn/Hugging Face/GitHub) · **`reach`** (server-less fetch CLI, the primary web backend: `web` = Jina, then a free local Chromium render, then Firecrawl, then curl; `search` = Exa, then SearXNG; `repo-wiki` = DeepWiki, `yt`, `rss`, `repo` = gh, `crawl` = Firecrawl.; no MCP servers. Paid backends run out of credits, so run `reach doctor` before a big build and lean on the free tiers) · **`agent-reach`** (only for gated social: Reddit/X/IG/FB via a cookie backend behind a burner profile) · `last30days` / `deep-research` (community sentiment) · `WebSearch`/`WebFetch` · GitHub MCP (releases/issues/discussions). Orchestrate these; do not reimplement them.
