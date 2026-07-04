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

## Commands

```
/docs <tool>                build a brief, or open it if it is still fresh
/docs refresh <tool>        re-fetch only the stale sections
/docs --stale               list every brief with per-section staleness
/docs list                  list all briefs
/docs import <tool> <path>  adopt an existing hand-written guide as a managed brief
```

## `/reach`, the fetch companion

`living-docs` ships with `reach`, a thin router over direct HTTP APIs and tools you
already have. No MCP server processes, no background daemons, nothing resident in RAM. It
is the fetch layer `/docs` runs on, and it stands alone as a CLI.

```
reach web <url>             clean markdown of any page (JS-rendered), via Jina Reader
reach search <query>        web search (Exa, with a Jina fallback)
reach repo-wiki <org/repo>  DeepWiki repo explainer
reach yt <url>              YouTube metadata + transcript
reach rss <feed>            latest items from a feed
reach repo <org/repo>       GitHub metadata + README
reach crawl map|site        managed JS crawl (Firecrawl) for the hard cases
reach doctor                what works right now
```

The keyless commands (`web`, `repo-wiki`, `yt`, `rss`, `repo`) work out of the box. Search
and the crawl paths use optional API keys, kept in `~/.reach/keys.env` (gitignored, chmod
600). Every path degrades instead of failing: Jina falls back to Firecrawl falls back to
raw curl, and `reach` prints which backend it used on stderr.

## Install

Requires [Claude Code](https://claude.com/claude-code). From a clone of this repo:

```bash
./install.sh
```

That symlinks `skills/docs` and `skills/reach` into `~/.claude/skills/`, puts `reach` on
your `PATH`, and creates `~/.reach/keys.env` from the example. The reference library
defaults to `~/docs-reference` (override with `DOCS_REFERENCE_DIR`). Then, in Claude Code:

```
/docs supabase
```

Optional, for a stronger `reach`: install `yt-dlp`, `gh`, and `pandoc`, and add any of
`EXA_API_KEY`, `JINA_API_KEY`, `FIRECRAWL_API_KEY` to `~/.reach/keys.env`.

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
