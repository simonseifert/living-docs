# Discovery playbook: how to fetch any surface

The order matters: cheap and structured first, expensive and scrape-y last. Fill `sources.yaml` URLs as you go.

## Step 0: Route the docs layer

Decide the docs provider once, record it in `sources.yaml`:

1. **First-party MCP connected?** Prefer it. It is authoritative and live. Known first-party doc/product MCPs in this environment: Vercel (`search_vercel_documentation`), Supabase (`search_docs`), Cloudflare, AWS (awslabs), Microsoft Learn, Hugging Face (`hf_doc_search`), GitHub (releases/issues/discussions). For these, set `docs_provider: first-party-mcp:<name>` and `ttl_days: on-demand` for the docs section (do not mirror what it serves live).
2. **Else Context7.** `resolve-library-id` then `query-docs`. Set `docs_provider: context7:<id>`. Good for popular libraries; thin for niche ones; no web fallback; docs-only.
3. **Else the tool's own `llms.txt`.** See Step 1.

**Auto-MCP docs platforms (detect and prefer over scraping):** if the docs are hosted on Mintlify, GitBook, or ReadMe, they auto-generate a free queryable MCP server + `llms-full.txt` + per-page markdown. Check for it (llms.txt presence, docs-site footer/headers) and consume the MCP or `llms-full.txt` directly. Docfork is a Context7 alternative (lower latency, per-project "Cabinets" that hard-lock the agent to a verified doc set).

**OSS repo internals + real usage (a dimension docs sites omit):** for open-source tools, `reach repo-wiki <org/repo>` (DeepWiki via Jina, no MCP or key) explains how a codebase actually works; `Grep` MCP (Vercel/grep.app, remote so no local RAM) surfaces real call sites for the recipes/gotchas sections. grep.app blocks direct calls, so that one genuinely needs its remote MCP.

Remember the Context7 gap: it covers code/library API docs only. Pricing, plans, status, changelog-as-news, actor/integration catalogs, and community are always your job regardless of docs provider.

## Step 1: llms.txt and the .md trick (the cheapest structured docs)

Probe these paths (helper: `scripts/probe_llmstxt.sh <domain>`):
- `https://<docs>/llms.txt` and `/llms-full.txt`
- `https://<docs>/docs/llms.txt` and `/docs/llms-full.txt`

`llms.txt` = a curated markdown index of doc links (use as a crawl manifest). `llms-full.txt` = the entire docs concatenated (can be tens of MB; save to `full/`, do not load wholesale, chunk on demand).

**The `.md` suffix trick:** many doc platforms (Mintlify, Docusaurus, VitePress) serve a clean markdown twin of any page by appending `.md` to the URL (verified on Apify: `docs.apify.com/api.md`, `apify.com/pricing.md`). Try it before scraping HTML.

**GitHub-hosted docs:** use `raw.githubusercontent.com/<org>/<repo>/<branch>/<path>` for clean source, or GitMCP (swap `github.com` → `gitmcp.io`) for live repo docs+search.

Reality check on llms.txt: adoption is real among dev tools (Apify, n8n, Supabase, Vercel, Stripe, Anthropic all publish one, verified) but uneven and unversioned. Always have a scrape fallback.

## Step 2: Fallbacks when there is no clean markdown (a cost ladder, cheapest first)

1. **Single-page clean read, incl. JS-rendered:** `reach web <url>` (wraps Jina Reader, free, no key, real server-side browser). Covers ~80% of scrape needs for $0. Advanced: Jina supports wait-for/remove selectors, cookies, and per-page structured extraction via headers (`X-Respond-With`).
2. **OSS source:** Repomix or gitingest for the whole repo; GitMCP for repo search; DeepWiki/Grep MCP for internals + real usage.
3. **Firecrawl (tier-5 escalation, INSTALLED, free tier ~1000 credits/mo, no rollover).** Use ONLY when the free ladder above genuinely fails:
   - (a) `reach crawl map <domain>` then `reach crawl site <url>` (Firecrawl) for a doc set / KB with NO sitemap AND NO predictable URL pattern (needs link-following, dedup, depth/path scoping, JS-generated links). This is Firecrawl's hardest-to-replicate win.
   - (b) SPA interaction Jina cannot do: clicks, infinite scroll, "load more", accordion/dropdown filters (e.g. Canny ideas boards, Stoplight docs).
   - (c) `firecrawl agent` / extract for structured JSON conforming to a schema.
   - Do NOT use it for large predictable-URL KB dumps: a 1214-page crawl is ~1214 credits and overshoots the free monthly cap, keep those on curl+pandoc. `firecrawl generate-llms.txt` can synthesize an llms.txt for a site that lacks one.

## Step 3: Product surfaces (the differentiator)

### Pricing
Fetch the pricing page; try `pricing.md` first. Capture: plan tiers + monthly/annual price, what each tier unlocks, free tier, hard limits, and pass-through/usage costs (per-SMS, per-1k-email, per-minute-voice, per-run). Table it.

### Changelog / news
Priority order for a machine-readable feed:
1. **RSS**: blog RSS (`/rss/`, `/feed`), or Canny changelog (`<board>/api/changelog/feed.rss`). Record the feed URL; poll `pubDate`.
2. **GitHub Releases** via GitHub MCP (`list_releases` / `get_latest_release`) for OSS tools.
3. **HTML changelog**: fetch-and-diff on a schedule when there is no feed (weakest; note it).

### Status
Record the status page URL. If Atlassian Statuspage: `https://status.<tool>.com/api/v2/status.json` (indicator), `summary.json` + `components.json` (component health), `history.rss`/`history.atom` (incidents). Do not copy live status into the brief; record how to check it and set `ttl_days: 1`.

### Available agents / actors / integrations
If the tool has a catalog, find its enumeration path:
- **Public catalog API** (best): e.g. Apify `GET https://api.apify.com/v2/store` (unauthenticated, paginated). Save a summary + taxonomy to the brief, the full list to `full/`.
- **Node/marketplace list** in docs (n8n nodes, GHL marketplace): capture the categories and notable items; note if there is no public enumeration endpoint (then it is a rendered-crawl job, mark `partial`).
- **Model/provider list**: capture from docs or the provider API.

### API contract
If an OpenAPI/Swagger spec exists, save to `full/openapi.json`, record its URL. If `info.version` is a timestamp/hash, record it as `change_detector` (poll that one string to detect API changes cheaply). Per-resource specs (e.g. Apify per-actor OpenAPI) are worth noting.

## Step 4: Community, social, news + knowledge base (scrape the open, search the gated)

Pull the open layer as real content, not just links. Save scraped bodies under `full/` and curate a short Community section into the brief.

**Preferred fetch layer: `agent-reach` (installed).** It is the internet-eyes router for social + web. Run `agent-reach doctor --json` to see which backend is live per platform. Zero-config channels (no login): GitHub, YouTube (transcripts via yt-dlp), RSS, V2EX, Bilibili, **free full-web semantic search via Exa (no API key)**, and **clean read of any page (incl. JS-rendered) via Jina Reader: `curl https://r.jina.ai/<URL>`**. Cookie-backed channels (Reddit, X/Twitter, Instagram, Facebook, LinkedIn depth) require a logged-in browser session; only enable those behind a burner browser profile. Use its output as the raw body, then curate. Fall back to `last30days` / `WebSearch` when a channel is off.

**Blogs / news:** find the RSS (`/rss`, `/feed`, `/blog/rss.xml`, or a Canny/Ghost/Substack feed). If there is no feed (many marketing blogs on Webflow have none, verified true for GHL), scrape the blog index for recent post URLs and fetch a few. Save to `full/community/`.

**Changelog:** a product changelog often has its own RSS even when the blog does not (e.g. Canny `<board>/api/changelog/feed.rss`, verified for GHL). Prefer it.

**YouTube:** resolve the channel_id (fetch the channel page and grep `"channelId":"UC..."` or `externalId`; if the page is a JS shell, use WebSearch for "<tool> youtube channel"), then read the channel RSS `https://www.youtube.com/feeds/videos.xml?channel_id=UC...` for the latest ~15 videos. Also capture the top third-party creator channels.

**Reddit + social:** raw anonymous `reddit.com/.rss` and `/.json` are IP-blocked from a datacenter (they return a "Blocked" page, sometimes even on HTTP 200, verified for r/gohighlevel). Reach them through `agent-reach` (its reddit/twitter/instagram/facebook channels use a logged-in cookie backend, so enable those only behind a burner profile), or `last30days`/`WebSearch` for sentiment without login. A Reddit OAuth "script" app or an Apify reddit-scraper actor is the deeper option, wire up only if asked.

**Record** each source in `sources.yaml` with its real `method` (`agent-reach`, `rss`, `youtube-rss`, `last30days`, `scrape`) and `fetchable` status.

### Knowledge-base / help-center crawl recipe

When a tool has a hosted help center / KB (Freshdesk, Zendesk, Intercom, GitBook), mirror it into `full/<kb>/` as markdown so the whole support corpus is grep-able offline. The pattern (verified on GHL's Freshdesk, ~1200 articles):

1. **Enumerate.** Most KBs are category → folder → article. Freshdesk: `/support/home` lists categories (`/support/solutions/<catId>`); `/support/solutions` and each category page list folders (`/support/solutions/folders/<id>`); each folder page lists articles (`/support/solutions/articles/<id>-<slug>`). Grep the article links from every folder page, dedup, into a manifest. (Zendesk exposes `/api/v2/help_center/articles.json`; Intercom/GitBook expose sitemaps.)
2. **Fetch politely + resumably.** One small helper per article: curl the page, slice the content container (Freshdesk = `fw-content--single-article`), `pandoc -f html -t gfm-raw_html` to clean markdown, write `full/<kb>/<id>-<slug>.md` (skip if it exists). Cap concurrency LOW (2-3): these portals rate-limit and serve block pages under load. Detect block pages (`too many requests` / `attention required` / `just a moment`), back off, and never write a junk file so the article stays in the redo set.
3. **Index + summarize.** Write `full/<kb>/INDEX.md` (category → folder → article) and fold the high-value bits (the sections relevant to the user's actual work) into the brief. Set the KB `sources.yaml` entry to `method: help-center-crawl`, `status: ok`.

A ready reference implementation is the GHL brief's `full/help-center/` and its fetch helper; reuse that shape for other Freshdesk KBs.

## Step 5: Synthesize, source, commit

Write `brief.md` (curate), write `sources.yaml` (every stale-able claim sourced + dated), update `INDEX.md`, `git add` + `git commit` the library. Do not push unless asked.

---

# Worked example A: Apify (agent-friendly, easy)

Apify is close to a best case because it was built for agent consumption. Verified surfaces:

| Surface | URL | Fetch | Note |
|---|---|---|---|
| docs index | `docs.apify.com/llms.txt` | GET | curated manifest of `.md` pages |
| docs full | `docs.apify.com/llms-full.txt` | GET | ~43 MB, save to `full/`, chunk |
| any doc page | append `.md` | GET | clean markdown twin (verified) |
| OpenAPI | `docs.apify.com/api/openapi.json` | GET | 3.1.2, 131 paths; `info.version` is timestamped → change detector |
| per-actor OpenAPI | `api.apify.com/v2/acts/{actor}/builds/default/openapi.json` | GET | public, per-actor input schema |
| **actor catalog** | `api.apify.com/v2/store?limit=&offset=&category=` | GET, **no auth** | ~34k actors, paginated, rich metadata. Crown jewel. |
| categories | derive from store items | aggregate | no standalone endpoint; ~20-value enum is stable |
| pricing | `apify.com/pricing.md` | GET | clean markdown |
| changelog | `apify.com/change-log` | scrape+diff | HTML-only, no feed (weak spot) |
| blog/news | `blog.apify.com/rss/` | RSS | clean feed, good news source |
| status | `status.apify.com/api/v2/summary.json` | GET | Atlassian Statuspage JSON |
| GitHub | `github.com/apify` | GitHub API | 235 repos: SDKs, CLI, Crawlee |
| MCP (live tools) | `mcp.apify.com` | auth | first-party agent tools; token-gated, document only |
| AGI / agentic pay | `agi.apify.com` | GET (HTML) | agents pay per-actor via x402/MPP; strategically notable |

Refresh design: poll `openapi.json` version string (API changes) + blog RSS + status JSON daily/weekly; re-pull `/v2/store` monthly (paginated); GitHub releases per repo. Only the changelog needs HTML scraping.

# Worked example B: GoHighLevel (hard, split feasibility)

GHL is the hard case: docs are split across retired v1 / dated v2 versions / newer v3, and much of the ecosystem is JS-heavy or auth-walled. Build for the split.

**Easy (automate this):**

| Surface | URL | Fetch | Note |
|---|---|---|---|
| **OpenAPI specs (gold)** | `github.com/GoHighLevel/highlevel-api-docs` | GitHub API / raw | CC0 public domain; ~45 per-product specs under `/apps/`, `/apps/v3/`, `/models/`. Mirror + diff on cron. |
| API docs portal | `marketplace.gohighlevel.com/docs/` | WebFetch (partial) | Docusaurus; for data use the GitHub specs instead |
| product changelog | `ideas.gohighlevel.com/api/changelog/feed.rss` | RSS | clean, ~10 latest items, poll often |
| API changelog | `marketplace.gohighlevel.com/docs/Changelog` | fetch+diff | flags breaking changes; no feed |
| help center | `help.gohighlevel.com` | WebFetch (partial) | stable article IDs; good for RAG |

**Hard / partial / off-limits (mark accordingly, do not brute-force):**

| Surface | Why | Handling |
|---|---|---|
| marketplace app catalog | SPA, no public list/search API | per-app `/integration/{id}` only; `partial` |
| ideas/roadmap board | Canny SPA; list API needs owner key | fetch individual posts; `partial` |
| status page | Better Stack, no confirmed feed, most components "not monitored" | scrape coarse HTML; `partial` |
| Stoplight portal | JS-only empty shell | use GitHub specs instead; skip |
| Facebook group / r/gohighlevel / dev Slack | login-walled | `auth-required`, links only |

**Operator-rule example:** if the user treats a tool as manual-only (e.g. a CRM they never let an agent write to), reproduce that rule as a callout at the top of the brief. The brief is reference, not an automation green-light. Secrets stay placeholders (`pit-xxxx`, `<locationId>`).

Bottom line: a self-updating GHL *API* reference (GitHub OpenAPI + two changelogs) is a cron job. The marketplace/roadmap/community layers are best-effort and partly off-limits. Scope to the API + changelogs; treat the rest as enrichment.
