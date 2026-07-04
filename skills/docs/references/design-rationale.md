# Why this skill is designed the way it is

Distilled from a landscape scan (existing skills, doc MCPs, prior art) plus live surface probes of Apify and GHL, run 2026-07-02.

## The gap this fills

The ecosystem splits into three silos, none of which is a durable per-tool living reference:
- **Docs-only**: Context7 (installed), GitMCP, Ref, docs-mcp-server, and generators (Skill_Seekers, llmstxt-to-skills). Cover API/library docs. Live or generated, but docs only.
- **Community/research**: `last30days` (installed), `deep-research`. Reddit/YouTube/HN, but point-in-time and topic-scoped, not saved per tool.
- **Freshness patterns**: ericbuess/claude-code-docs (read-triggered git-pull, ~3h) is the best auto-update mechanism, but mirrors one source.

**The Context7 gap:** Context7 indexes only code/library API docs and snippets. It does NOT cover pricing, plans, status, changelog-as-news, available actors/integrations, or community, unless those pages happen to live inside the indexed docs site (they usually do not). So Context7 is roughly the API-reference third of "know this tool inside out." The other two thirds (product surfaces + curated community, persisted) is the whitespace this skill occupies.

## The prior art that got deleted (the load-bearing lesson)

Gordon Beeming built almost exactly this (a global trigger + a `tech-research` orchestrator that spawned research subagents and stored two-tier findings in a git repo) and then gutted it. Three failure modes:
1. **Auto-trigger tax**: it ran on every session, including prose and refactors. "The feel of the tool changed." He removed the auto-trigger from global CLAUDE.md.
2. **Scope creep**: the trigger file became a catalog of every possible misunderstanding.
3. **Duplication**: Context7 and other MCPs already research docs on demand.

Design consequences, enforced by this skill:
- **Proactive when task-relevant, but never a global per-session hook.** Invoke it when the task is genuinely about a specific tool (and thanks to the foundation model, that is usually a cheap open-or-patch, not a rebuild). What killed the prior implementation was an ALWAYS-ON trigger that ran on every session including prose and refactors. So the narrow rule: no session-start hook and no global CLAUDE.md import that fires every message. "Pay the cost when the task wants the value, not on every session."
- **Do not duplicate live doc tools.** Lean on Context7/first-party MCPs for the docs layer. The value-add is the layer they do not cover.
- **Keep the trigger surface small.** One skill, clear usage, no sprawling instruction file.

## Curate, do not dump (the evidence)

LangChain benchmarked four configs and found a **condensed, hand-curated guide beat raw-docs-in-a-tool and was ~2.5x cheaper**; raw-docs-alone underperformed because the agent stopped at surface descriptions instead of following links. Separately, human-curated context beat LLM-generated dumps (which actually *lowered* task success and raised cost). So:
- The brief is a condensed, opinionated guide (mental model + recipes + gotchas + pricing + limits), not a docs dump.
- Raw dumps (llms-full.txt, OpenAPI, catalogs) go to `full/` for drill-down only, never loaded wholesale.
- Two-tier by design: `brief.md` in context, `full/` on disk.

## Why a local git repo

The reference library is a plain git-tracked directory you own, so it versions cleanly and syncs across machines however you like (git remote, Syncthing, etc). Keep it OUT of any directory a sandboxed sub-agent cannot write: some note apps and cloud-synced folders block subprocess writes on macOS. A normal project directory works best; sub-agents write there directly.

## Freshness, honestly

Different surfaces rot at different rates, so TTL is per-section, not per-tool. Refresh is on-invoke plus a staleness check (`/docs --stale`), not a cron, to avoid the auto-trigger trap. A cheap `change_detector` (OpenAPI version string, RSS pubDate) is polled before any expensive re-fetch.

On community (v2): scrape the genuinely open layer as real content, not just links, blogs/news RSS, the changelog feed, YouTube channel RSS, and the vendor's whole help center / KB crawled into `full/`. Reddit and social are reachable through the `last30days` skill or WebSearch even when raw anonymous fetches are IP-blocked from a datacenter (Reddit's `.rss`/`.json` return a "Blocked" page here), so route them there rather than declaring them unreachable. Only truly login-walled surfaces (private FB groups, member Slack/Discord history, gated dashboards) stay `auth-required`. The honest move is to mark a surface `auth-required`/`partial` when it really is, not to pretend coverage and not to give up on one that a different path can reach.
