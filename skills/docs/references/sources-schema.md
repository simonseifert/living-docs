# sources.yaml schema

`sources.yaml` is the machine-readable half of a brief. It is what makes freshness *managed* instead of guessed. `scripts/stale.py` reads it; `/docs refresh` acts on it.

One file per tool at `~/docs-reference/<tool>/sources.yaml`.

## Fields

```yaml
tool: apify
canonical_domain: apify.com
docs_root: https://docs.apify.com
github: apify/apify-sdk-js          # org or org/repo; omit if none
docs_provider: llms.txt             # first-party-mcp:<name> | context7:<id> | llms.txt | scrape
change_detector:                    # cheapest signal that "something changed"
  type: openapi_version             # openapi_version | rss | github_releases | http_etag | none
  url: https://docs.apify.com/api/openapi.json
  field: info.version               # for openapi_version: the JSON path to the version string
  last_value: "v2-2026-07-01T115402Z"

sections:
  - name: docs
    url: https://docs.apify.com/llms.txt
    method: llms.txt                 # how to re-fetch: mcp | context7 | llms.txt | md-suffix | rss | youtube-rss | github-api | statuspage-json | store-api | help-center-crawl | agent-reach | jina-reader | last30days | scrape
    last_fetched: 2026-07-02
    ttl_days: 30                     # "on-demand" allowed as a string when served live by an MCP
    status: ok                       # ok | partial | auth-required | unverified
  - name: pricing
    url: https://apify.com/pricing.md
    method: md-suffix
    last_fetched: 2026-07-02
    ttl_days: 30
    status: ok
  - name: changelog
    url: https://blog.apify.com/rss/
    method: rss
    last_fetched: 2026-07-02
    ttl_days: 7
    status: ok
  - name: status
    url: https://status.apify.com/api/v2/summary.json
    method: statuspage-json
    last_fetched: 2026-07-02
    ttl_days: 1
    status: ok
  - name: actors
    url: https://api.apify.com/v2/store
    method: store-api
    last_fetched: 2026-07-02
    ttl_days: 30
    status: ok
    note: unauthenticated enumeration, ~34k actors, paginate limit/offset
  - name: community
    url: https://www.reddit.com/r/apify/
    method: last30days
    last_fetched: 2026-07-02
    ttl_days: 30
    status: partial
    note: reddit body auth-required; captured links + last30days sweep only
```

## Rules

- **Every brief section that can go stale needs a `sources` entry.** If a claim in `brief.md` has no source entry, it is `unverified` and should be marked as such in the brief.
- **`status: auth-required`** means we recorded the URL but cannot fetch the body unattended (private FB group, gated Reddit, member Slack). List it, do not scrape it.
- **`change_detector`** is the cheap pre-check on refresh: poll it first; if unchanged, skip the expensive re-fetch and just restamp. OpenAPI version strings and RSS `pubDate` are ideal.
- **TTL defaults:** status 1d · changelog/news 7d · pricing 30d · actors/integrations 30d · api/docs 30d (or `on-demand` if a live MCP serves them) · overview/mental-model 180d. Override per tool.
- **Dates are `YYYY-MM-DD`, UTC.** `stale.py` compares against today.
