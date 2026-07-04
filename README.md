# living-docs

**A Claude Code skill that builds and maintains a living reference brief for any tool in your stack.**

Not just API docs. For each tool you work with, `/docs` fetches the whole picture, features, pricing, changelog, status, available integrations, gotchas, and curated community resources, and writes it to a local, agent-facing markdown brief with a machine-readable freshness manifest. Build it once; after that it is check-deltas-and-patch, never rebuild.

It ships with a companion fetch tool, `/reach`, that does the actual internet fetching without standing up any MCP servers.

## The gap it fills

Doc MCPs like Context7 give an agent live **API documentation**. They do not cover pricing, plans, status, changelog-as-news, a service's list of integrations/actors, or community gotchas, and they do not persist anything between sessions. `living-docs` owns that layer: one curated file per tool, on disk, kept fresh on demand.

## How it works

Each tool gets a directory with two files (plus raw dumps for drill-down):

```
<library>/<tool>/
  brief.md       # the curated, agent-facing guide you actually read
  sources.yaml   # every stale-able claim -> source URL + last_fetched + ttl + a change_detector
  history.md     # append-only build/refresh log
  full/          # raw dumps (llms-full.txt, openapi.json, KB mirror) for drill-down only
```

Two ideas make it work:

- **Curate, do not dump.** The brief is a condensed, opinionated guide (mental model, recipes, gotchas, pricing, limits), not a raw docs dump. Raw material lives in `full/` and is never loaded wholesale. A curated guide beats raw-docs-in-a-tool and costs far less context.
- **Build once, then patch.** Every stale-able fact maps to a `sources.yaml` entry with a cheap `change_detector` (an OpenAPI version string, an RSS date, a GitHub release tag). A refresh polls the detectors first and re-fetches only the sections that actually moved. The first run is the only expensive one.

## Usage

```
/docs <tool>              # build a brief, or open it if fresh
/docs refresh <tool>      # re-fetch only the stale sections
/docs --stale             # list every brief with per-section staleness
/docs list                # list all briefs
/docs import <tool> <path>  # adopt an existing hand-written guide as a managed brief
```

A fully worked, public example ships at [`examples/apify/brief.md`](examples/apify/brief.md).

## `/reach`, the fetch companion

`reach` is a thin, server-less router: one CLI over direct HTTP APIs and already-installed tools, with no MCP server processes and no background daemons. `/docs` uses it as its fetch layer.

```
reach web <url>            # clean markdown of any page (JS-rendered) via Jina Reader
reach search <query>       # web search (Exa, or Jina fallback)
reach repo-wiki <org/repo> # DeepWiki repo explainer
reach yt <url>             # YouTube metadata + transcript
reach rss <feed>           # latest items from a feed
reach repo <org/repo>      # GitHub metadata + README
reach crawl map|site       # managed JS crawl (Firecrawl) for the hard cases
reach doctor               # what works right now
```

The keyless commands (`web`, `repo-wiki`, `yt`, `rss`, `repo`) work out of the box. `search` and the escalation/crawl paths use optional API keys (see `skills/reach/keys.env.example`).

## Install

Requires [Claude Code](https://claude.com/claude-code). From a clone of this repo:

```bash
./install.sh
```

That symlinks `skills/docs` and `skills/reach` into `~/.claude/skills/`, puts `reach` on your `PATH`, and creates `~/.reach/keys.env` from the example. The reference library defaults to `~/docs-reference` (override with `DOCS_REFERENCE_DIR`). Then, in Claude Code:

```
/docs supabase
```

Optional (better `reach`): install `yt-dlp`, `gh`, `pandoc`, and add any of `EXA_API_KEY`, `JINA_API_KEY`, `FIRECRAWL_API_KEY` to `~/.reach/keys.env`.

## Design notes

See [`skills/docs/references/design-rationale.md`](skills/docs/references/design-rationale.md) for why this is built the way it is (the prior art that got deleted for auto-running every session, the curate-not-dump evidence, the freshness model).

## License

MIT. Built with Claude Code.
