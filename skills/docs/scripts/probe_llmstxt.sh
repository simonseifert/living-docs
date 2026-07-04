#!/usr/bin/env bash
# Probe the standard machine-readable-docs URL shapes for a domain.
# Usage: probe_llmstxt.sh docs.apify.com
#        probe_llmstxt.sh apify.com
# Prints, per candidate URL: HTTP status, content-type, and size.
# Helps decide the docs-fetch method before any scraping.

set -u
dom="${1:-}"
if [ -z "$dom" ]; then
  echo "usage: probe_llmstxt.sh <domain>   (e.g. docs.apify.com)" >&2
  exit 2
fi
dom="${dom#http://}"; dom="${dom#https://}"; dom="${dom%%/*}"

candidates=(
  "https://$dom/llms.txt"
  "https://$dom/llms-full.txt"
  "https://$dom/docs/llms.txt"
  "https://$dom/docs/llms-full.txt"
  "https://$dom/index.md"
  "https://$dom/api/openapi.json"
  "https://$dom/openapi.json"
  "https://$dom/sitemap.xml"
)

printf "%-8s %-28s %s\n" "STATUS" "CONTENT-TYPE" "URL"
for u in "${candidates[@]}"; do
  # -sI HEAD request; fall back to GET range if HEAD is blocked
  hdr="$(curl -sIL --max-time 15 "$u" 2>/dev/null | tr -d '\r')"
  code="$(printf '%s\n' "$hdr" | awk '/^HTTP/{c=$2} END{print c}')"
  ctype="$(printf '%s\n' "$hdr" | awk -F': ' 'tolower($1)=="content-type"{v=$2} END{print v}')"
  if [ -z "$code" ]; then
    # some servers reject HEAD; try a 1-byte GET
    code="$(curl -s -o /dev/null -w '%{http_code}' -r 0-0 --max-time 15 "$u" 2>/dev/null)"
    ctype="(GET)"
  fi
  printf "%-8s %-28s %s\n" "${code:-ERR}" "${ctype:0:28}" "$u"
done

echo
echo "tip: for any HTML doc page, also try appending .md (e.g. https://$dom/some/page.md)"
