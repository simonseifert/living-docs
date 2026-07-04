---
tool: Apify
category: web-scraping-automation-platform
one_liner: Cloud platform + marketplace ("Actors") for web scraping, data extraction, and agent automation; run 34k+ prebuilt tools or ship your own, all via one REST API / SDK / MCP.
last_verified: 2026-07-02
sdk_package:
  js: apify-client (client) / apify (SDK) / apify-cli (CLI)
  python: apify-client (client) / apify (SDK)
docs_provider: apify (first-party; llms.txt + .md twins + OpenAPI)
sources: sources.yaml
---

## TL;DR
- Apify = serverless cloud for running **Actors** (containerized scraper/automation programs) plus a **Store** of ~34.5k prebuilt ones. You rent/run them; Apify handles infra, proxies, storage, billing, scheduling.
- One unified **REST API** (`api.apify.com/v2`) underlies everything. Official clients: `apify-client` (JS + Python), CLI `apify-cli`, first-party **MCP server** (`mcp.apify.com`) for agents.
- Auth = a single **API token** (`Authorization: Bearer <api-token>`). Store catalog (`/v2/store`) is **unauthenticated**.
- Billing is **prepaid platform usage** metered in **Compute Units (CU = 1 GB-RAM-hour)** + proxy/storage/transfer. Plans: Free $0, Starter $29, Scale $199, Business $999/mo.
- Best agent-facing entry points: `/v2/store` (browse actors, no auth), per-actor OpenAPI, and `mcp.apify.com` (token-gated tool surface). Autonomous-payment entry: `agi.apify.com` (x402 / MPP).
- Cheap change detector: `docs.apify.com/api/openapi.json` → `info.version` is a timestamp (`v2-2026-07-01T115402Z`).

## Mental model / core concepts
| Concept | What it is |
| --- | --- |
| **Actor** | A serverless program in a Docker container. Takes JSON input, runs, writes output. The unit of everything on Apify. Identified as `username/name` or `username~name` in API paths. |
| **Run** | One execution of an Actor. Has status (`READY`→`RUNNING`→`SUCCEEDED`/`FAILED`/`ABORTED`/`TIMED-OUT`), a default dataset, key-value store, and request queue. |
| **Dataset** | Append-only tabular result storage (the scraped rows). Fetch as JSON/CSV/XLSX. Each run gets a default one. |
| **Key-value store** | Blob/JSON storage keyed by string (INPUT, OUTPUT, screenshots, files). Each run gets a default one. |
| **Request queue** | Managed URL frontier for crawls (dedup, retries, in-progress tracking). |
| **Apify Store** | Public marketplace of ~34.5k Actors, community-built, free or rented monthly. Browsable unauth via `/v2/store`. |
| **Task** | A saved Actor + input config you can re-run/schedule without repassing input. |
| **Standby** | Actor running as a persistent HTTP server for low-latency, always-on API responses. |

**Platform vs SDK vs API vs CLI vs Crawlee**: keep these straight:
- **Platform** = the hosted cloud (Console, runs, storage, proxy, scheduler, billing).
- **API** = the REST surface (`api.apify.com/v2`); source of truth, everything else wraps it.
- **SDK** (`apify`, JS/Python) = library you use *inside* an Actor (read input, push data, manage storage, proxy).
- **Client** (`apify-client`, JS/Python) = library you use *outside* to drive the platform (start runs, pull datasets).
- **CLI** (`apify-cli`) = local dev: `apify create`, `apify run`, `apify push`, login.
- **Crawlee** = Apify's open-source scraping *library* (Node + Python). Runs anywhere; not Apify-specific, but Actors are usually built on it. Store/run/proxy are platform features; crawling logic is Crawlee.

## Auth & setup
Single API token from Console → Settings → Integrations. Use as Bearer header (preferred) or `?token=` query param.

```bash
# Header (preferred)
curl -H "Authorization: Bearer <api-token>" https://api.apify.com/v2/users/me
# Query param (works, but leaks in logs: avoid)
curl "https://api.apify.com/v2/users/me?token=<api-token>"
```

```bash
# CLI minimal init
npm install -g apify-cli
apify login            # paste <api-token>
apify create my-actor  # scaffold from template
apify run              # run locally
apify push             # deploy to platform
```

```js
// JS client
import { ApifyClient } from 'apify-client';
const client = new ApifyClient({ token: '<api-token>' });
```

```python
# Python client
from apify_client import ApifyClient
client = ApifyClient('<api-token>')
```

## Common tasks / recipes

**Run an Actor via raw API (sync, returns dataset items directly):**
```bash
curl -X POST \
  -H "Authorization: Bearer <api-token>" -H "Content-Type: application/json" \
  -d '{"startUrls":[{"url":"https://example.com"}]}' \
  "https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items"
```
Async variant: `POST /v2/acts/{actor}/runs` → poll `GET /v2/actor-runs/{runId}` → read `defaultDatasetId`.

**Run an Actor via client + get dataset items:**
```js
const run = await client.actor('apify/website-content-crawler').call({
  startUrls: [{ url: 'https://example.com' }],
});
const { items } = await client.dataset(run.defaultDatasetId).listItems();
```
```python
run = client.actor('apify/website-content-crawler').call(
    run_input={'startUrls': [{'url': 'https://example.com'}]})
items = client.dataset(run['defaultDatasetId']).list_items().items
```

**Get dataset items directly (paginate + format):**
```bash
curl -H "Authorization: Bearer <api-token>" \
  "https://api.apify.com/v2/datasets/<datasetId>/items?format=json&clean=true&limit=1000&offset=0"
```

**Enumerate the Store (UNAUTH, paginated):**
```bash
curl "https://api.apify.com/v2/store?limit=100&offset=0&category=SOCIAL_MEDIA&search=instagram&sortBy=popularity"
# data.total = full count; page with limit/offset. sortBy: popularity|newest|relevance|lastEdit
```

**Per-actor OpenAPI (exact input schema for any Actor):**
```bash
curl "https://api.apify.com/v2/acts/apify~website-content-crawler/builds/default/openapi.json"
# -> full input/endpoint schema; server is https://api.apify.com/v2. Best way for an agent to learn an Actor's inputs.
```

**Set up the MCP server (agent tools, token-gated):**
```jsonc
// Claude/Cursor mcp config: remote server
{
  "mcpServers": {
    "apify": {
      "url": "https://mcp.apify.com",
      "headers": { "Authorization": "Bearer <api-token>" }
    }
  }
}
```
The MCP server exposes tools to search the Store, run Actors, and read datasets. Autonomous agents can also pay per-call without an account via `agi.apify.com` (x402 / MPP protocols).

## Features (what it can do)
- **Run 34.5k+ prebuilt Actors**: scrapers for Google Maps, Instagram, TikTok, YouTube, Amazon, LinkedIn, plus generic crawlers.
- **Build & deploy your own** Actors (any language via Docker; JS/Python SDK + templates; Web IDE or `apify push`).
- **Managed storage**: datasets, key-value stores, request queues; export JSON/CSV/XLSX/HTML.
- **Apify Proxy**: residential, datacenter, and SERP proxies with rotation.
- **Scheduling, webhooks, integrations**: cron schedules, run-finished webhooks, native Zapier/Make/n8n/LangChain/LlamaIndex hooks.
- **Standby mode**: Actors as always-on HTTP APIs for real-time responses.
- **Anti-blocking**: browser fingerprinting, session pools, automatic retries (via Crawlee).
- **Agent-native surfaces**: first-party MCP server, per-actor OpenAPI, AGI agentic-payment endpoint, Agent Skills.
- **Monetization**: publish Actors to Store and earn (community pays out >$1M/mo).

## Available actors
Enumerate via the unauthenticated, paginated **`/v2/store`** endpoint (`data.total ≈ 34,498` as of 2026-07-02). Filter with `category=`, `search=`, `sortBy=` (`popularity|newest|relevance|lastEdit`), page with `limit`/`offset`.

**Category enum (~20):** `AI`, `AGENTS`, `AUTOMATION`, `BUSINESS`, `DEVELOPER_TOOLS`, `ECOMMERCE`, `INTEGRATIONS`, `JOBS`, `LEAD_GENERATION`, `MARKETING`, `MCP_SERVERS`, `NEWS`, `OPEN_SOURCE`, `OTHER`, `REAL_ESTATE`, `SEO_TOOLS`, `SOCIAL_MEDIA`, `SPORTS`, `TRAVEL`, `VIDEOS`.

**Live category sizes (sample, 2026-07-02):** LEAD_GENERATION 13,804 · ECOMMERCE 7,881 · SOCIAL_MEDIA 7,641 · AI 5,774 · AGENTS 1,997 · MCP_SERVERS 1,019. (Categories overlap; totals sum past 34.5k.)

**Notable Actors (by popularity):**
| Actor ID | Title |
| --- | --- |
| `compass/crawler-google-places` | Google Maps Scraper |
| `apify/instagram-scraper` | Instagram Scraper |
| `apify/website-content-crawler` | Website Content Crawler (LLM/RAG ingestion) |
| `clockworks/tiktok-scraper` | TikTok Scraper |
| `streamers/youtube-scraper` | YouTube Scraper |

For the full machine-readable list, snapshot `/v2/store` into `full/` (paginate to `data.total`).

## Pricing, limits & quotas
Monthly subscription grants **prepaid platform usage**; overage billed pay-as-you-go (paid plans continue on overage, Free plan is blocked until next cycle). Unused usage does **not** roll over. Save 10% annual. (from `apify.com/pricing.md`, 2026-07-02)

| Plan | Monthly | Annual/mo | Included usage/mo | CU price | Max RAM | Max concurrent runs | Support |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Free | $0 | $0 | $5 | $0.20/CU | 16 GB | 25 | Community |
| Starter | $29 | $26 | $29 | $0.20/CU | 64 GB | 32 | Chat |
| Scale | $199 | $179 | $199 | $0.16/CU | 256 GB | 128 | Priority chat |
| Business | $999 | $899 | $999 | $0.13/CU | 512 GB | 256 | Account manager |

**Compute Unit:** 1 CU = 1 GB RAM running for 1 hour. Actor run cost = CU consumption + proxy + storage + data transfer + retries.
**Proxy:** residential $7–8/GB · datacenter 5–500 IPs included then $0.6–1/IP · SERP $1.7–2.5 / 1,000.
**Add-ons:** concurrent run $5/run · Actor RAM $1/GB · priority support $100 · personal training $150/hr.
**Discounts:** students 30% off Starter/Scale · startups 30% off Scale · nonprofits/universities custom.
**Enterprise:** custom plans, SLAs, guaranteed data (`apify.com/contact-sales`).
**Rate limits:** Global 250,000 requests/min per token (per IP for unauthenticated calls). Default per-resource limit is 60 req/s (Actor/run/dataset/key-value store); Run-Actor and run-task-async endpoints are higher at 400 req/s; key-value-store record CRUD is 200 req/s. `429` = back off; responses carry `X-RateLimit-*` headers. Reference: `docs.apify.com/api/v2` rate-limiting section.

## Gotchas / anti-patterns
- **`~` vs `/` in Actor IDs:** REST paths use `username~name` (`apify~website-content-crawler`); clients accept `username/name`. Mixing them in a raw URL 404s.
- **`run-sync-get-dataset-items` has a timeout ceiling** (~5 min / 300s). Long crawls must run async + poll, or you'll get truncated/timed-out responses.
- **Prepaid usage expires monthly**: no rollover. Don't prepay Business expecting to bank credits.
- **Rented Actors cost extra** beyond CU: their monthly rental is separate (deducted from prepaid usage on paid plans; Free plan gets trial only).
- **Free plan blocks on overage** mid-cycle; paid plans keep running and invoice the overage. Don't assume a hard stop on paid plans.
- **Don't load `llms-full.txt` (~43MB) whole.** Use `llms.txt` index + the `.md` twin of the specific page, or per-actor OpenAPI.
- **Token in query string leaks** into logs/proxies. Use the `Authorization` header.
- **Store totals overlap categories**: summing category `data.total`s double-counts; use the top-level `/v2/store?limit=1` `data.total` for the real count.
- **Changelog is HTML-only** (no RSS/JSON). Use the blog RSS for posts and the OpenAPI `info.version` timestamp as the actual change detector.

## Troubleshooting
| Symptom | Likely cause / fix |
| --- | --- |
| `401 Unauthorized` | Missing/invalid token, or wrong header. Use `Authorization: Bearer <api-token>`. |
| `404` on `/v2/acts/...` | Actor ID uses `/` instead of `~` in a raw URL, or Actor is private/renamed. |
| Run `SUCCEEDED` but dataset empty | Wrong input schema: pull the per-actor OpenAPI to confirm field names; check the run's log + key-value `OUTPUT`. |
| `run-sync` truncates / times out | Job exceeds sync ceiling (~300s). Switch to async `POST /runs` + poll. |
| `429 Too Many Requests` | Per-token rate limit. Exponential backoff; batch reads with higher `limit`. |
| Runs blocked / "usage limit reached" | Prepaid usage exhausted. Free = blocked till next cycle; paid = raise billing limit in Console. |
| Getting blocked by target site | Enable Apify Proxy (residential), lower concurrency, use the Actor's proxy config. |
| MCP tools not appearing | Server needs `Authorization: Bearer <api-token>` header; verify at `mcp.apify.com`. |

## Changelog / status watch
- **Change detector (cheap):** `docs.apify.com/api/openapi.json` → `info.version` is a timestamp. Current: `v2-2026-07-01T115402Z`. Diff this string to know if the API surface moved.
- **Blog / release posts:** RSS at `https://blog.apify.com/rss/`.
- **Product changelog:** `https://apify.com/change-log` (HTML only, no RSS/JSON; scrape and diff if needed).
- **Status:** `https://status.apify.com` + JSON `https://status.apify.com/api/v2/status.json` (`status.indicator`, currently `none` = "All Systems Operational") and `/api/v2/summary.json` for component detail.

## Community & resources (public)
- **Docs:** `https://docs.apify.com` · LLM index `docs.apify.com/llms.txt` · full `llms-full.txt` (~43MB, don't load whole) · every page has a `.md` twin.
- **API reference:** `https://docs.apify.com/api/v2` · OpenAPI `docs.apify.com/api/openapi.json`.
- **GitHub org:** `https://github.com/apify`: `apify-sdk-js`, `apify-sdk-python`, `apify-cli`, `apify-client-js`, `apify-client-python`, `crawlee` (+ `crawlee-python`).
- **Academy (free course):** `https://docs.apify.com/academy`.
- **Discord:** `https://discord.com/invite/jyEM2PRvMU` (Apify & Crawlee community).
- **YouTube:** `https://www.youtube.com/@apify`.
- **Blog:** `https://blog.apify.com`.
- **MCP server (agent tools):** `https://mcp.apify.com`: *token-gated (auth-walled)*.
- **AGI / agentic payments:** `https://agi.apify.com` (x402 / MPP).
- **Console (product):** `https://console.apify.com`: *auth-walled*.

## Source map
All stale-able claims above are tracked with URL, method, TTL, and last-fetched date in `sources.yaml` (change detector = OpenAPI `info.version`).