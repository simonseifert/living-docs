<div align="center">

# living-docs

**Your agent's long-term memory for every tool in your stack.**

A Claude Code skill that builds a living reference brief for any tool you work with,
then keeps it current with cheap delta-checks instead of rebuilds.

[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
![Claude Code skill](https://img.shields.io/badge/Claude%20Code-skill-black)
![Server-less](https://img.shields.io/badge/MCP%20servers-0-black)

</div>

---

Doc tools like Context7 tell your agent how an API works *right now*. That is one slice.
They do not carry pricing, plans, status, changelog-as-news, the service's own list of
integrations and actors, the version pins that bite you, or the gotchas people only learn
in production. And they forget everything the moment the session ends.

`living-docs` owns that layer. One curated markdown file per tool, on disk, in git, kept
fresh on demand. Build it once; after that it is check-deltas-and-patch, never rebuild.

```
you: /docs supabase
                                          first run  ── fetch docs, pricing, changelog,
                                                        limits, gotchas, community  →  brief.md
                                                                                   →  sources.yaml
you (three weeks later): /docs refresh supabase
                                          later runs ── poll cheap change-detectors,
                                                        re-fetch only what actually moved
```

## Why it holds up

Two ideas do the work.

**Curate, do not dump.** The brief is a condensed, opinionated guide, the mental model plus
recipes, gotchas, pricing, and real limits, not a raw docs dump. Raw material lives in
`full/` and is never loaded wholesale. A curated guide beats raw-docs-in-a-tool and costs a
fraction of the context.

**Build once, then patch.** Every stale-able fact maps to a `sources.yaml` entry with a
cheap `change_detector`: an OpenAPI version string, an RSS date, a GitHub release tag. A
refresh polls the detectors first and re-fetches only the sections that actually changed.
The first run is the only expensive one.

## What a brief looks like on disk

```
<library>/<tool>/
  brief.md       the curated, agent-facing guide you actually read
  sources.yaml   every stale-able claim → source URL + last_fetched + ttl + change_detector
  history.md     append-only build/refresh log
  full/          raw dumps (llms-full.txt, openapi.json, KB mirror) for drill-down only
```

A fully worked, public example ships at
[`examples/apify/brief.md`](examples/apify/brief.md), a brief for the Apify scraping
platform built by this skill. It is the depth bar.

## Keeping briefs fresh, cheaply

Maintenance has to stay cheap or the library rots. Every layer below costs nothing or runs
on a free model, and your main agent is never in the loop.

| Step | Script | Cost |
|---|---|---|
| What is stale? `last_fetched + ttl_days` per section | `stale.py` (`--lint`, `--summary`) | free, local |
| What actually moved? GitHub release tag, npm/PyPI version, RSS date, page hash | `detect.py` | free, ~10 s for 90 tools |
| Did the facts change? Compare the old section with the re-fetched page | `groq_refresh.py` | free: local Ollama first (`--provider auto`), Groq free tier as fallback |
| Do it unattended every night | `refresh_batch.py` | free on your own GPU |
| Tell me what drifted | `docs_freshness.py` | free, one ntfy push |

**The nightly refresh** (`refresh_batch.py --max 60 --commit` from a systemd or launchd
timer, plus a weekly `--all-tools` sweep) picks the moved and stale sections of the tools
you actually used recently, re-fetches each, asks a local model (`gpt-oss:20b`) whether the
facts changed, patches only real changes, commits, and sends one summary. `git revert`
undoes any night. It is built for running unattended against pages it does not trust:

- a section is only marked verified if the fetched page contains that section's own
  distinctive facts (numbers, versions, names), so a bot wall or the wrong page cannot
  silently "confirm" stale facts;
- patches that add instruction-like text, add a URL found in neither the old section nor
  the page, drop dates, or change the section length wildly are rejected;
- it only fetches http(s), never shells out with a string, and can yield the GPU to
  another resident model (`DOCS_GPU_YIELD_TO`);
- when a version moves, it lists every other line of the brief that still names the old
  version, instead of guessing a find-and-replace.

## Making agents actually use it

The finding that shaped this: in a blind test, a fresh agent asked an n8n question went
straight to web search, although a curated n8n brief sat on disk. An agent decides from
the skill listing alone, and "use it when the task is about a tool" does not tell it
*which* tools have briefs. `scripts/describe.py` writes your tool names into the skill's
`when_to_use` (most active first, within Claude Code's 1,536-character listing cap). After
that, the same test opened the brief first and answered from it. Run it whenever you add
a tool; the nightly job does too.

Inside a big brief or a 12 MB help-center mirror, agents search instead of loading:
`docs-search "webhook retry" --tool n8n` (SQLite FTS5 over every brief and raw dump,
incremental, curated briefs ranked above raw dumps) returns the few passages that matter.

## Commands

```
/docs <tool>                build a brief, or open it if it is still fresh
/docs <tool> --deep         also mirror the full catalog, OpenAPI, help center, wider community
/docs refresh <tool>        re-fetch only the stale or moved sections
/docs search <query>        full-text search across all briefs and raw dumps
/docs absorb                file facts you flagged in your notes into the right brief
/docs --stale | --lint      staleness per section | manifest health
/docs list                  list all briefs
/docs import <tool> <path>  adopt an existing hand-written guide as a managed brief
```

## `/reach`, the fetch companion

`living-docs` ships with `reach`, a thin router over direct HTTP APIs and tools you
already have. No MCP server processes, no background daemons, nothing resident in RAM. It
is the fetch layer `/docs` runs on, and it stands alone as a CLI.

```
reach web <url>             clean markdown of any page (JS-rendered), Jina Reader -> local headless Chromium
reach search <query>        web search (Exa, then self-hosted SearXNG, then Jina)
reach psearch <query>       Perplexity Search API with citations
reach repo-wiki <org/repo>  DeepWiki explainer of how a codebase actually works
reach yt <url>              YouTube metadata + transcript
reach rss <feed>            latest items from a feed
reach repo <org/repo>       GitHub metadata + README
reach instagram <user>      public Instagram posts through Apify
reach reddit <query>        public Reddit search through Apify
reach x-public <query>      public X search (Apify Actor, no cookies)
reach x-followers <handle>  public X audience relations (Apify Actor)
reach x <query>             deeper X access through agent-reach and a burner profile
reach linkedin <url>        LinkedIn profile, company or posts (Apify, no cookies)
reach doc <file>            local Word/PPT/Excel/PDF/EPUB -> markdown, keyless
reach transcribe <audio>    audio/video -> text (self-hosted whisper.cpp, Groq fallback)
reach crawl map|site        managed JS crawl (Firecrawl) for the hard cases
reach doctor                what works right now
```

`repo-wiki` is worth calling out: it pulls a [DeepWiki](https://deepwiki.com) explainer of a
repository (architecture, data flow, key modules), which beats a bare README when you are
writing accurate gotchas and recipes for a tool. It reads DeepWiki through Jina keylessly,
and falls back to the DeepWiki MCP (which also answers free-form `ask_question` queries).

The keyless commands (`web`, `repo-wiki`, `yt`, `rss`, `repo`) work out of the box. Search
and the crawl paths use optional API keys, kept in `~/.reach/keys.env` (gitignored, chmod
600). Every path degrades instead of failing: `web` goes Jina, then a free local headless
Chromium, then Firecrawl, then curl, and `reach` prints which backend served it on stderr.

The public X routes run through Apify Actors: keyed API, no cookies, no account
risk. They leave the cookie-backed `reach x` route intact. Both default to 20
results, accept a bounded `REACH_APIFY_LIMIT` from 1 to 200, send `APIFY_TOKEN`
only in an authorization header, and take `REACH_X_TWEET_ACTOR` /
`REACH_X_FOLLOWER_ACTOR` so the route is not tied to one Actor vendor.

"Twitter" and "X" are trademarks of X Corp; these routes are not affiliated with
or endorsed by X Corp.

## Install

Requires [Claude Code](https://claude.com/claude-code). From a clone of this repo:

```bash
./install.sh
```

That symlinks `skills/docs` and `skills/reach` into `~/.claude/skills/` (an existing real
copy is moved to `~/.claude/skills-backup/` first), puts `reach` and `docs-search` on your
`PATH`, and creates `~/.reach/keys.env` from the example. The reference library
defaults to `~/docs-reference` (override with `DOCS_REFERENCE_DIR`). Then, in Claude Code:

```
/docs supabase
```

**Requirements:** Python 3.10+ with SQLite FTS5 (standard in most builds). PyYAML is
recommended (`pip install pyyaml`); without it a small fallback parser is used.

**Optional:** [Ollama](https://ollama.com) with `gpt-oss:20b` for free local refreshes
(fits a 16 GB GPU). `yt-dlp`, `gh` and Playwright for a stronger `reach`. Any of
`EXA_API_KEY`, `JINA_API_KEY`, `FIRECRAWL_API_KEY`, `GROQ_API_KEY` (free tier) or
`DEEPSEEK_API_KEY` in `~/.reach/keys.env`. A self-hosted or access-controlled
[ntfy](https://ntfy.sh) for pings: on public ntfy.sh anyone who knows a topic can read it.

## What this is, and what it is not

- **It is** a durable, curated, self-refreshing knowledge layer for the tools *you* use,
  the parts a docs MCP skips and never remembers.
- **It is not** a docs MCP replacement. Point-in-time API lookups are what Context7 and
  friends are for. `living-docs` sits next to them and covers the rest.
- **Secrets are always placeholders.** Briefs never contain a real key, and `reach` reads
  keys from a gitignored file, never from a brief or the repo.

## Design notes

[`skills/docs/references/design-rationale.md`](skills/docs/references/design-rationale.md)
covers why it is built this way: the prior art that got deleted for auto-running every
session, the curate-not-dump evidence, and the freshness model.

## License

MIT. Built with [Claude Code](https://claude.com/claude-code).
