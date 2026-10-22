---
name: reach
description: >-
  Server-less internet fetch for agents | read any web page (JS-rendered),
  search the web, pull YouTube transcripts, RSS feeds, GitHub repos/READMEs,
  DeepWiki repo explainers, and managed JS crawls. One CLI (`reach`) that
  shells out to direct HTTP APIs + already-installed tools (Jina Reader, Exa,
  yt-dlp, gh, Firecrawl), with NO MCP servers and NO background daemons (zero
  RAM footprint). Use when you need to fetch or search public internet content
  from the command line. Also does account-safe social with no cookies:
  LinkedIn profiles/companies/posts (HarvestAPI), Instagram, TikTok and Facebook
  page posts (ScrapeCreators), Google Maps reviews (Bright Data), Reddit and
  public X (Apify Actors), each printing which vendor answered and what it cost.
  Is the single front door for fetching; cookie-gated deep social (Facebook
  search, and X with a session) routes to `agent-reach` under the hood (needs a
  burner Chrome profile).
trigger: /reach
---

# reach | server-less internet fetch

A thin router over direct HTTP APIs and installed CLIs. Everything is stateless and on-demand: no MCP server processes, no daemons, no always-on tool schemas. Built this way on purpose for RAM-limited machines: prefer a direct API/CLI call over standing up an MCP server.

Command: `reach` (on PATH via `~/.local/bin/reach`; source at `~/.claude/skills/reach/scripts/reach`).

## Commands

```
reach web <url>             clean markdown of any page (JS-rendered): Jina -> local Chromium   [keyless]
reach setup                 one-time: install headless Chromium for the local web tier
reach repo-wiki <org/repo>  DeepWiki repo explainer (how a codebase actually works)    [keyless]
reach search <query>        web search: Exa -> SearXNG -> Jina                         [EXA_API_KEY / SEARXNG_URL optional]
reach psearch <query>       Perplexity Search API, cited results                       [needs PERPLEXITY_API_KEY]
reach yt <url>              YouTube metadata + auto transcript (yt-dlp)                 [keyless]
reach rss <feed-url>        latest ~15 items from an RSS/Atom feed                      [keyless]
reach repo <org/repo>       GitHub metadata + README (gh)                              [keyless, uses gh auth]
reach instagram <user> [n]  Instagram posts: ScrapeCreators -> Apify                   [SCRAPECREATORS_API_KEY / APIFY_TOKEN]
reach tiktok <user> [n]     TikTok videos with plays/likes/shares (ScrapeCreators)     [SCRAPECREATORS_API_KEY]
reach facebook-page <page> [n] Facebook PAGE posts (ScrapeCreators, no cookies)        [SCRAPECREATORS_API_KEY]
reach reviews <maps-url> [days] Google Maps reviews (Bright Data, async, slow)         [BRIGHTDATA_API_KEY]
reach reddit <query>        Reddit search (scope with r/<sub> <query>), no cookies       [uses APIFY_TOKEN]
reach x-public <query>      Public X search (Apify Actor, no cookies)                 [uses APIFY_TOKEN]
reach x-public user <handle> Public X timeline (Apify Actor, no cookies)                [uses APIFY_TOKEN]
reach x-followers <handle>  Public followers/following (Apify Actor)                   [uses APIFY_TOKEN]
reach doc <file>            Word/PPT/Excel/PDF/EPUB/ODF/RTF/CSV -> markdown             [keyless, local]
reach transcribe <audio>    audio/podcast/video -> text (self-hosted whisper.cpp, Groq fallback) [WHISPER_SERVER_URL / GROQ_API_KEY]
reach x <query>             X/Twitter (routes to agent-reach)                          [needs burner setup]
reach linkedin <url>        LinkedIn profile or company: HarvestAPI -> Apify            [HARVESTAPI_KEY / APIFY_TOKEN]
reach linkedin posts <url>  LinkedIn post history w/ engagement: HarvestAPI -> Apify   [HARVESTAPI_KEY / APIFY_TOKEN]
reach facebook <query>      Facebook search (routes to agent-reach)                    [needs burner setup]
reach crawl map <domain>    discover a site's URLs (Firecrawl)                         [uses credits]
reach crawl site <url>      managed JS crawl to markdown (Firecrawl)                   [uses credits]
reach doctor                what works right now, with each vendor's live balance
```

`reach` is the **single front door**: each command auto-picks its backend, so callers never choose a tool. The social routes use keyed vendor APIs with no cookie and no account, so they cannot get an account restricted. The remaining cookie-gated platforms (`facebook`, and `x` for logged-in depth) route to `agent-reach`; until a burner Chrome profile + logins exist, those print the exact enable step instead of failing silently.

## Which tool and vendor for what

| Question | Use |
|---|---|
| Who is this person / company? | `intel` (`intel linkedin <url>` for one LinkedIn profile, corpus first) |
| What does an account publish, what works, how does it compare? | corpus, via `intel content ...` (stored, reusable, audited) |
| A quick one-off look: a page, a few recent posts, a transcript | `reach` |

| Platform | Preferred vendor, cost | Fallback | Commands |
|---|---|---|---|
| LinkedIn profile / company | HarvestAPI, $0.004 per lookup | Apify actor | `reach linkedin`, `intel linkedin` |
| LinkedIn posts | HarvestAPI, $0.004 per page of ~100 | Apify actor | `reach linkedin posts`, `intel content` |
| Instagram posts | ScrapeCreators, 1 credit (~$0.002) per 12 posts | Apify actor | `reach instagram`, `intel content` |
| TikTok videos | ScrapeCreators, 1 credit per 10 | none | `reach tiktok`, `intel content` |
| Facebook page posts | ScrapeCreators, 1 credit per 3 | none | `reach facebook-page`, `intel content` |
| YouTube | yt-dlp, free | | `reach yt`, `intel content` (Shorts) |
| Google Maps reviews | Bright Data, 1 credit per record (5k free/month), ~10 min | none | `reach reviews` (first live run returned an error record: treat as experimental) |
| Reddit, public X | Apify actors | | `reach reddit`, `reach x-public` |

**Balances:** `reach doctor` shows HarvestAPI dollars, ScrapeCreators credits, the Apify
plan/cap and whether Bright Data accepts jobs (all free reads); `intel content health`
checks the corpus pipeline. Check before a large job and whenever a result looks empty.

**Every result states its source and cost.** `reach` prints `reach: served by <vendor>`
and `charged $X` / `N credit(s)` on stderr; `intel` prints `# source: <vendor> (paid,
$X), as of <date>` (`vendor` and `cost_usd` in `--json`). Carry vendor, cost and as-of
date into whatever you hand back. A private or missing target does not fall back to a
second vendor (it would bill for the same miss). `REACH_PAGES=1..5` (default 1) caps
billed pages per call; `REACH_BD_MAX` caps Bright Data records (default 20).

## Design rules

- **Direct API / CLI over MCP servers.** Local MCP servers cost RAM; remote MCP servers cost always-loaded context. A stateless curl/CLI call costs neither. Only reach for an MCP when a source has no usable direct endpoint (e.g. grep.app blocks direct calls; use its remote MCP if you need it).
- **Keyless by default.** web / repo-wiki / yt / rss / repo / crawl need no key of ours. `search` uses Exa if keyed, else a self-hosted SearXNG (`SEARXNG_URL`), else keyless Jina. Optional `JINA_API_KEY` raises the web-read rate limit. Keys live in `~/.reach/keys.env` (gitignored, chmod 600), never in a brief, node, or repo.
- **Local files stay local.** `reach doc` converts Word/PowerPoint/Excel/PDF/EPUB/ODF on this machine via anydoc (pure Rust, no ML, no service, no key, median <5ms). Firecrawl's hosted /parse does the same conversion, but these are usually a client's contract or RFP — do not send one to a third party to read it. The one exception is a scanned/image-only PDF, which needs OCR; anydoc says so explicitly and the error names the hosted fallback.
- **Cost ladder for reading pages:** `reach web` (free Jina) for single pages incl. JS → `reach crawl` (Firecrawl, credits) ONLY when you need URL discovery with no sitemap, or SPA click/scroll interaction. Do not `crawl` a large predictable-URL KB (`reach web` per URL is free for that).
- **One front door, explicit X routes.** `reach instagram`, `reach reddit`, `reach x-public`, and `reach x-followers` run through Apify Actors directly. `reach x` remains the deeper cookie-backed route through `agent-reach`; adding Actor routes does not replace it. Use `reach x-public` for public posts and `reach x-followers` for public audience relations without a browser account.

## Public X without a browser account

`reach x-public` (search and timelines) and `reach x-followers` (audience
relations) run through Apify Actors: a keyed API call, no cookies, no account
risk. `reach x` remains the deeper cookie-backed route via agent-reach; these
do not replace it.

```bash
reach x-public '"web scraping" lang:en'
reach x-public user apify
reach x-followers apify                     # or: following | verified_followers
```

Newline-delimited JSON. 20 items by default; `REACH_APIFY_LIMIT` accepts 1-200.
The Actors are configurable via `REACH_X_TWEET_ACTOR` and
`REACH_X_FOLLOWER_ACTOR` — the defaults work, but Actors get deprecated and
repriced, so the route is not welded to one vendor. Check current Store pricing
before a large run. `APIFY_TOKEN` travels in an authorization header, never a
URL. Treat returned profile data as personal data: minimise what you keep and
carry provenance into anything downstream.


## Fallbacks and MCP backups

Every path degrades instead of failing (the multi-backend idea, borrowed from agent-reach):

- `reach web`: Jina Reader (keyless retry if the key is out of credits; live refetch if Jina serves a stale cached snapshot) -> local headless Chromium + trafilatura (`scripts/reach-render.py`, free, JS, gets past most Cloudflare challenges) -> Firecrawl scrape (1 credit) -> plain `curl` + extraction (no JS). Each tier is accepted only on HTTP 200 with real text that is not a bot-wall page. stderr says `reach: served by <tier>`; if every tier fails it exits 1 and lists the reason per backend (out of credits, DNS, challenge page...). `REACH_FRESH=1` skips Jina's cache, `REACH_NO_BROWSER=1` skips Chromium. Reddit URLs (incl. old.reddit / redd.it) skip Jina, which blocks anonymous Reddit reads, and go straight to Chromium on www.reddit.com, which returns the post plus its comments for free. The Chromium tier needs `uv`; run `reach setup` once per machine to download the headless Chromium matching the pinned Playwright. If it is missing, `reach web` offers to install it on a terminal, prints that hint otherwise, and `reach doctor` reports it.
- `reach search`: Exa API -> self-hosted SearXNG (`SEARXNG_URL`) -> Jina search (`s.jina.ai`). Automatic.
- `reach transcribe`: self-hosted whisper.cpp server (`WHISPER_SERVER_URL`, started with `--convert`) -> Groq Whisper. Automatic. Both URL settings take a comma-separated list, e.g. a loopback address and a VPN address for the same box.
- `reach repo-wiki`: Jina reads DeepWiki; if it fails, use the DeepWiki MCP (`ask_question` also lets you query the repo, which the flat read cannot).

Free remote MCPs are registered as backups / gap-fillers (remote = no local RAM, fine per the "MCP is ok for backup" rule):

- **Exa MCP** (`mcp.exa.ai`) backs up `reach search`.
- **DeepWiki MCP** (`mcp.deepwiki.com`) backs up `reach repo-wiki` and adds `ask_question`.
- **Grep MCP** (`mcp.grep.app`) is the ONLY way to code-search across ~1M repos (grep.app blocks direct calls); use it for real call sites when writing gotchas/recipes.
- **Firecrawl** has both a CLI (what `reach crawl` uses) and an MCP; the CLI is enough.

Rule of thumb: try `reach` (direct, fast, no RAM) first; reach for an MCP when the direct path fails or a capability only exists there (Grep, DeepWiki `ask_question`).

## Relationship to other tools

This is the self-owned, RAM-free layer for the STABLE primitives (they rarely change, so owning them is cheap). It replaces reliance on the `agent-reach` glue for everything except the fragile cookie-based social channels. The `/docs` skill uses `reach` as its web-read / search / crawl backend.
