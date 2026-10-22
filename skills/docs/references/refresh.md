# Refreshing a brief

Loaded by `/docs refresh <tool>`, or when an opened brief turns out stale for the question at hand.

## Steps

Detection is free (pure local Python, no model). Only the actual re-read and patch
spends a model, and that model is a cheap one, never the agent's own tokens.

1. Read the tool's `sources.yaml`. Compute staleness per section (`now - last_fetched` vs `ttl_days`). `scripts/stale.py <tool>` does this. (Free.)
2. Re-fetch only stale sections (or the ones named in `--section`). Cheap first: poll the change_detector (OpenAPI version string, RSS pubDate, GitHub release tag) before re-scraping anything. Fetch with `reach`.
3. **Compare with a cheap model, not the agent.** `scripts/groq_refresh.py --old <section>.md --fetched <slice>.md --section <name> --tool <tool>` sends the current section plus the freshly-fetched source to a cheap OpenAI-compatible model and returns JSON `{changed, summary, updated_section}`. Providers: `auto` (default: the local model if Ollama answers, else Groq with a stderr notice; brief sections can hold private client context, so local is preferred), `groq` (`openai/gpt-oss-120b`, free tier, caps request size so send a focused slice), `local` (free `gpt-oss:20b` on your own Ollama, no size cap), `deepseek` (stronger judgment, needs `DEEPSEEK_API_KEY`). Apply `updated_section` only when `changed` is true, and eyeball the diff.
4. Restamp `last_fetched` (and flip `status` to `ok`) for every section you re-verified, including the ones that did not change.
5. **Log the changes.** Prepend a dated entry to `<tool>/history.md` listing exactly what moved (e.g. "pricing Starter $20 -> $24; n8n 2.28 -> 2.29; status/community restamped, no change"). If nothing changed, log "checked, no change". Mirror a one-liner into `CHANGELOG.md`.
6. Commit with `git commit -m "docs: refresh <tool> (<sections>)"`.

**After a version bump** (`detect.py` says moved): also grep the whole brief for the old version string. It usually sits in more than one place (frontmatter `pinned_version`, install tips, the detector note); fix every mention or the brief contradicts itself.
