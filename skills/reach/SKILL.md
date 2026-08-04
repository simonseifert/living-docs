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
  Instagram, Reddit, and public X data (via Apify actors). Is the single front
  door for fetching: cookie-gated deep social (X/Twitter, Facebook, LinkedIn)
  uses the same surface via `reach x|linkedin|facebook`, which routes to
  `agent-reach` under the hood (needs a burner Chrome profile).
trigger: /reach
---

# reach | server-less internet fetch

A thin router over direct HTTP APIs and installed CLIs. Everything is stateless and on-demand: no MCP server processes, no daemons, no always-on tool schemas. Built this way on purpose for RAM-limited machines: prefer a direct API/CLI call over standing up an MCP server.

Command: `reach` (on PATH via `~/.local/bin/reach`; source at `~/.claude/skills/reach/scripts/reach`).

## Commands

```
reach web <url>             clean markdown of any page (JS-rendered) via Jina Reader   [keyless]
reach repo-wiki <org/repo>  DeepWiki repo explainer (how a codebase actually works)    [keyless]
reach search <query>        web search via Exa API                                     [needs EXA_API_KEY]
reach yt <url>              YouTube metadata + auto transcript (yt-dlp)                 [keyless]
reach rss <feed-url>        latest ~15 items from an RSS/Atom feed                      [keyless]
reach repo <org/repo>       GitHub metadata + README (gh)                              [keyless, uses gh auth]
reach instagram <user>      Instagram posts (Apify actor, no cookies/account risk)     [needs APIFY_TOKEN]
reach reddit <query>        Reddit search (scope with r/<sub> <query>), no cookies       [uses APIFY_TOKEN]
reach x-apify <query>       Public X search through Xquik X Tweet Scraper                [uses APIFY_TOKEN]
reach x-apify user <handle> Public X timeline through Xquik X Tweet Scraper              [uses APIFY_TOKEN]
reach x-followers <handle>  Public followers/following through Xquik X Follower Scraper  [uses APIFY_TOKEN]
reach doc <file>            Word/PPT/Excel/PDF/EPUB/ODF/RTF/CSV -> markdown             [keyless, local]
reach transcribe <audio>    audio/podcast/video -> text (Groq Whisper)                 [needs GROQ_API_KEY]
reach x <query>             X/Twitter (routes to agent-reach)                          [needs burner setup]
reach linkedin <url|query>  LinkedIn (routes to agent-reach)                           [needs burner setup]
reach facebook <query>      Facebook (routes to agent-reach)                           [needs burner setup]
reach crawl map <domain>    discover a site's URLs (Firecrawl)                         [uses credits]
reach crawl site <url>      managed JS crawl to markdown (Firecrawl)                   [uses credits]
reach doctor                what works right now
```

`reach` is the **single front door**: each command auto-picks its backend, and the cookie-gated platforms (`x`/`linkedin`/`facebook`) route to `agent-reach` under the hood, so callers never choose a tool. Until a burner Chrome profile + logins are set up, those three print the exact enable step instead of failing silently.

## Design rules

- **Direct API / CLI over MCP servers.** Local MCP servers cost RAM; remote MCP servers cost always-loaded context. A stateless curl/CLI call costs neither. Only reach for an MCP when a source has no usable direct endpoint (e.g. grep.app blocks direct calls; use its remote MCP if you need it).
- **Keyless by default.** web / repo-wiki / yt / rss / repo / crawl need no key of ours. Only `search` (Exa) needs a key. Optional `JINA_API_KEY` raises the web-read rate limit. Keys live in `~/.reach/keys.env` (gitignored, chmod 600), never in a brief, node, or repo.
- **Local files stay local.** `reach doc` converts Word/PowerPoint/Excel/PDF/EPUB/ODF on this machine via anydoc (pure Rust, no ML, no service, no key, median <5ms). Firecrawl's hosted /parse does the same conversion, but these are usually a client's contract or RFP — do not send one to a third party to read it. The one exception is a scanned/image-only PDF, which needs OCR; anydoc says so explicitly and the error names the hosted fallback.
- **Cost ladder for reading pages:** `reach web` (free Jina) for single pages incl. JS → `reach crawl` (Firecrawl, credits) ONLY when you need URL discovery with no sitemap, or SPA click/scroll interaction. Do not `crawl` a large predictable-URL KB (curl+pandoc is free for that).
- **One front door, explicit X routes.** `reach instagram`, `reach reddit`, `reach x-apify`, and `reach x-followers` run through Apify Actors directly. `reach x` remains the deeper cookie-backed route through `agent-reach`; adding Actor routes does not replace it. Use `reach x-apify` for public posts and `reach x-followers` for public audience relations without a browser account.

## Public X via Xquik Actors

Use [Xquik X Tweet Scraper](https://apify.com/xquik/x-tweet-scraper) for public searches and account timelines:

```bash
reach x-apify '"web scraping" lang:en'
reach x-apify user apify
```

Use [Xquik X Follower Scraper](https://apify.com/xquik/x-follower-scraper) for public audience relations:

```bash
reach x-followers apify
reach x-followers apify following
reach x-followers apify verified_followers
```

Both commands return newline-delimited JSON. They cap runs at 20 items by default. Set `REACH_APIFY_LIMIT` from 1 to 200 when a different bound is justified. Check each Actor's current Store pricing before a larger run. Keep `APIFY_TOKEN` only in the protected key file; `reach` sends it in an authorization header and never places it in a URL. Treat returned profile data as personal data, minimize collection, and keep provenance with downstream summaries.

Xquik is an independent third-party service. Not affiliated with X Corp. "Twitter" and "X" are trademarks of X Corp.

## Fallbacks and MCP backups

Every path degrades instead of failing (the multi-backend idea, borrowed from agent-reach):

- `reach web`: Jina Reader -> Firecrawl scrape (JS, 1 credit) -> raw `curl` + pandoc (no JS). Automatic; it prints which fallback it used on stderr.
- `reach search`: Exa API -> Jina search (`s.jina.ai`). Automatic.
- `reach repo-wiki`: Jina reads DeepWiki; if it fails, use the DeepWiki MCP (`ask_question` also lets you query the repo, which the flat read cannot).

Free remote MCPs are registered as backups / gap-fillers (remote = no local RAM, fine per the "MCP is ok for backup" rule):

- **Exa MCP** (`mcp.exa.ai`) backs up `reach search`.
- **DeepWiki MCP** (`mcp.deepwiki.com`) backs up `reach repo-wiki` and adds `ask_question`.
- **Grep MCP** (`mcp.grep.app`) is the ONLY way to code-search across ~1M repos (grep.app blocks direct calls); use it for real call sites when writing gotchas/recipes.
- **Firecrawl** has both a CLI (what `reach crawl` uses) and an MCP; the CLI is enough.

Rule of thumb: try `reach` (direct, fast, no RAM) first; reach for an MCP when the direct path fails or a capability only exists there (Grep, DeepWiki `ask_question`).

## Relationship to other tools

This is the self-owned, RAM-free layer for the STABLE primitives (they rarely change, so owning them is cheap). It replaces reliance on the `agent-reach` glue for everything except the fragile cookie-based social channels. The `/docs` skill uses `reach` as its web-read / search / crawl backend.
