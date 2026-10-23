---
name: docs
description: 'Build and maintain a local, living reference brief for any tool, service, API or SDK in the stack (n8n, Apify, Supabase, Next.js, Stripe, anything). Covers far more than API docs: features, pricing, changelog, status, integrations/actors, gotchas and curated community, plus a sources manifest with per-section freshness. Use it whenever the current task is genuinely about a specific tool: open its brief, refresh it if stale, or build it if missing.'
when_to_use: 'Trigger phrases: "learn <tool>", "research our stack", "know <tool> inside out", "fetch the latest docs for <tool>", "what can <tool> do", "refresh the <tool> brief", "search the docs for", or starting real work against a tool. Run scripts/describe.py once you have briefs: it lists your tools here so agents open the brief before searching the web. Never wire it into a session-start hook.'
argument-hint: "<tool> [--deep] | refresh <tool> | search <query> | absorb | --stale | --lint | list | import <tool> <path>"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(${CLAUDE_SKILL_DIR}/scripts/*) Bash(docs-search *)
---

# /docs: living reference briefs for any tool in the stack

One curated brief per tool, on disk, kept fresh: features, pricing, changelog, status, integrations, gotchas, community. Context7 and doc MCPs cover live API docs; briefs cover everything they miss. Answer from the brief instead of re-searching the web.

**Library right now:**
!`python3 ${CLAUDE_SKILL_DIR}/scripts/stale.py --summary 2>/dev/null || true`

## Answering a question about a tool (the common case)

1. **Search, do not load.** `docs-search "<terms>" --tool <tool>` returns the few relevant passages from the brief and its raw `full/` dumps. Read a whole `brief.md` only when you need the overview; never load a `full/` file wholesale.
2. **Check freshness of what you rely on.** `python3 ${CLAUDE_SKILL_DIR}/scripts/stale.py <tool>`. If the section you are answering from is stale and the fact could have moved (price, version, limit), say so, verify it live, and patch the brief (`references/refresh.md`). Old-but-stable facts (concepts, recipes) are fine.
3. **Answer from the brief and say so** ("per the local n8n brief, verified 2026-10-22"). Gotchas and operator-rule callouts at the top of a brief are binding.

No brief for the tool, and the task is real work against it? Build one (`references/build.md`). A one-off trivia question does not justify a build.

## Usage

```
/docs <tool>                     # open the brief if fresh; else refresh or build it
/docs <tool> --deep              # build with the --deep extras (references/build.md)
/docs refresh <tool>             # re-fetch only stale or moved sections (references/refresh.md)
/docs refresh <tool> --section pricing,changelog | --all
/docs search <query> [--tool T]  # full-text search, same as `docs-search`
/docs absorb                     # file facts flagged in the vault into briefs (references/automation.md)
/docs review                     # work through _review/: changes the nightly job proposed but did not apply
/docs --stale | --lint           # per-section staleness | manifest health (scripts/stale.py)
/docs list                       # INDEX.md
/docs import <tool> <path>       # adopt an existing hand-written guide as a managed brief
```

## Where things live

- **Skill** (logic, templates, scripts): `~/.claude/skills/docs/`
- **Library** (the data, git): `~/docs-reference/<tool>/` with `brief.md` (the curated guide), `sources.yaml` (every stale-able claim: url, last_fetched, ttl_days, status, change_detector), `history.md` (newest-first log), `full/` (raw dumps, drill-down only). `INDEX.md` lists all briefs; keep each row's Notes under ~40 words.
- Keep the library in a plain directory sub-agents can write (a normal git repo). Avoid note apps or cloud-synced folders that block subprocess writes on macOS; if you want a copy there, mirror it from the main session. Sub-agents never write to a restricted path.

## Rules

1. **Curate, do not dump.** A brief is a condensed, opinionated guide (mental model, recipes, gotchas, pricing, limits), never a docs dump. Raw material goes to `full/`.
2. **Lean on what exists.** For live API docs prefer a connected first-party MCP, then Context7, then `llms.txt`. The brief adds what those miss.
3. **Secrets are placeholders, always** (`pit-xxxx`, `<locationId>`, `<api-key>`). The library is git-tracked.
4. **Preserve operator rules.** If the user has a standing rule about a tool (for example "this CRM is manual-only, never let an agent write to a live account"), reproduce it as a prominent callout at the top of that tool's brief. Briefs are reference, not an automation green-light.
5. **Every stale-able fact has a source and a date** in `sources.yaml`; otherwise mark it `unverified`. Never bypass an auth wall.
6. **Proactive yes, global hook no.** Opening or patching a brief because the task is genuinely about tool X is right. Never wire this into a session-start hook or always-loaded import: the prior version died from firing on every session (`references/design-rationale.md`).

## References (load on demand)

- `references/build.md`: building a brief, `--deep`, audit trail, default TTLs, which tools to compose
- `references/refresh.md`: the refresh steps and the cheap-model compare (`groq_refresh.py`)
- `references/automation.md`: `/docs absorb`, the nightly auto-refresh, the weekly ping
- `references/discovery-playbook.md`: per-surface fetch playbook (llms.txt probe, KB crawl recipe, Apify + GHL worked examples)
- `references/brief-template.md`, `references/sources-schema.md`, `references/example-brief.md`: the brief skeleton, manifest schema, depth/tone bar
- `references/design-rationale.md`: why this design
