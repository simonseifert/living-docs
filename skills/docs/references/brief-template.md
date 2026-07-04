# Brief template

Instantiate this into `~/docs-reference/<tool>/brief.md`. Curate hard: every section is condensed and opinionated, not a docs dump. Delete sections that genuinely do not apply (a pure library has no "actors/integrations"; a SaaS has no "SDK"). Keep it scannable: headers, tables, short bullets, copy-paste snippets.

Match the depth and tone of `example-brief-ghl.md`. A good brief is the thing you would want open in a second monitor while building against the tool.

---

```markdown
---
tool: <name>
category: <saas | api | library | framework | ipaas | infra | ...>
one_liner: <what it is in one sentence>
last_verified: <YYYY-MM-DD>
sdk_package: <npm/pip/etc name>            # omit if N/A
pinned_version: <version we target>        # omit if N/A
docs_provider: <first-party-mcp:name | context7:<id> | llms.txt | scrape>
sources: sources.yaml
---

# <Tool>: reference brief

> ⚠️ OPERATOR RULE (if any): <e.g. this tool is manual-only, never let an agent write to a live account. Reference only, not an automation green-light.> 
> Secrets in this file are placeholders (`<api-key>`, `pit-xxxx`). Never commit a real credential.

## TL;DR
2-3 sentences: what it is, who it is for, when we reach for it, the one thing that most surprises people.

## Mental model / core concepts
The vocabulary and primitives. The hierarchy (account → project → resource). The 5-10 nouns you must know to read the docs. This is the section that stays true longest.

## Auth & setup
Env vars, key types, the minimal init snippet, the header trio that actually works. Note auth gotchas (which token type for which job, expiry, refresh).

## Common tasks / recipes
Copy-paste snippets for the 5-10 things we actually do with this tool. Prefer real, runnable calls with placeholder secrets. This is the highest-value section.

## Features (what it can do)
Condensed map of the product surface. For a SaaS: the modules. For a library: the main APIs. Enough that we know what is possible without reading all the docs.

## Available agents / actors / integrations
Only if the tool has a catalog (Apify actors, n8n nodes, marketplace apps, model list). How to enumerate them (API endpoint if public), the category taxonomy, the notable ones. Point at `full/` for the full machine list.

## Pricing, limits & quotas
Plan tiers, free tier, rate limits, pass-through/usage costs, the limits that bite in production. The stuff doc-MCPs never tell you. Table form.

## Gotchas / anti-patterns / deprecated
"Use X not Y." Version pins. Footguns. Deprecations with dates. Field-experience failures (cite issue refs if from claude-mem/past runs). This section is worth more than the happy-path docs.

## Troubleshooting
Symptom → cause → fix. Common error codes and what they really mean.

## Changelog / status watch
Changelog + status URLs, the RSS/JSON feed to poll, the cheap change-detector (e.g. OpenAPI version string). "What changed since <date>" one-liner. Do not paste live status; say how to check it.

## Community & resources (public)
Official: docs, support KB, developer portal, changelog board. Community: subreddit, top YouTube channels, official Discord/Slack invite, notable third-party tools/snapshots/MCP servers. Best guides. Links only. Auth-walled sources are listed but marked as such.

## Source map
Points to `sources.yaml`. One line: "Freshness and source URLs are tracked in sources.yaml; run `/docs refresh <tool>` to update."
```
