# Gold-standard brief: what "good" looks like

A concrete, fully public example ships with this skill at **`examples/apify/brief.md`** (a brief for the Apify web-scraping platform, built by this skill). Read it before writing a brief for a comparably deep tool. It is the depth bar.

A brief for a substantial platform should reach roughly this level; a brief for a small library will be much shorter, and that is fine.

## Why it is the standard

- **Deep, not broad-and-shallow.** Feature sections explain behavior and quirks, not just feature names.
- **The API section is operational.** Auth token types and when to use each, the exact working header set, rate limits with the real numbers, key endpoints grouped by resource, real copy-paste calls with placeholder secrets.
- **A gotchas/anti-patterns layer worth more than the happy path.** Version pins, footguns, deprecations with dates, field-experience failures.
- **A troubleshooting section** keyed by symptom and error code.
- **Pricing, limits, and quotas** that bite in production, the stuff a docs-only tool never tells you.
- **Operator rule up top when one applies** (e.g. "this tool is manual-only, never let an agent write to a live account"), reproduced as a callout so no agent reads the brief as an automation green-light.
- **Secrets are placeholders throughout.**
- **Quick-reference tables** at the end (plan/feature matrix, HTTP status meanings, base URLs).

## What the skill adds on top of a hand-written guide

A hand-written guide usually scatters freshness as prose ("verified 2026-06-20", "confirm at the pricing page"). The managed version adds `sources.yaml`: every stale-able claim (pricing, rate limits, endpoints, deprecation dates) mapped to a source URL + `last_fetched` + `ttl_days`, plus a `change_detector`. That is the difference between a snapshot and a living reference: `/docs refresh <tool>` can then update just the stale sections instead of a human re-reading the whole thing.
