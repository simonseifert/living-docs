#!/usr/bin/env bash
# Probe the standard machine-readable-docs URL shapes for one or more domains.
# Usage: probe_llmstxt.sh docs.apify.com
#        probe_llmstxt.sh apify.com n8n.io        (probes host + docs.<host>)
#        probe_llmstxt.sh --wide apify.com        (also developers.<host>)
# Prints, per candidate URL: HTTP status, content-type, verdict, and URL.
# llms.txt / llms-full.txt bodies are validated (a 200 is not trusted):
#   FAKE(html), FAKE(robots), WEAK(no links), OK(N links), plus INJECTION?
# Helps decide the docs-fetch method before any scraping.

set -u

usage() {
  cat <<'EOF'
usage: probe_llmstxt.sh [--wide] [-h|--help] <domain> [domain...]

  <domain>   bare domain or host, e.g. apify.com or docs.apify.com
             probes the host itself and docs.<host> (unless it already
             starts with docs.)
  --wide     also probe developers.<host>
  -h, --help show this text

Candidates: llms.txt, llms-full.txt, .well-known/llms.txt, docs/llms*.txt,
index.md, pricing.md, .well-known/skills/index.json, /mcp, openapi, sitemap.
Verdicts for llms*.txt: FAKE(html) FAKE(robots) WEAK(no links) OK(N links),
and INJECTION? when prompt-injection phrases appear. "exists?" for /mcp on
non-HTML 200, 400, 401, 405 or 406.
EOF
}

wide=0
doms=()
for a in "$@"; do
  case "$a" in
    -h|--help) usage; exit 0 ;;
    --wide) wide=1 ;;
    *) doms+=("$a") ;;
  esac
done
if [ "${#doms[@]}" -eq 0 ]; then
  usage >&2
  exit 2
fi

hosts=()
add_host() {
  local h
  for h in "${hosts[@]:-}"; do [ "$h" = "$1" ] && return; done
  hosts+=("$1")
}
for d in "${doms[@]}"; do
  d="${d#http://}"; d="${d#https://}"; d="${d%%/*}"
  [ -z "$d" ] && continue
  add_host "$d"
  case "$d" in
    docs.*|developers.*) ;;
    *)
      add_host "docs.$d"
      [ "$wide" -eq 1 ] && add_host "developers.$d"
      ;;
  esac
done

# Classify an llms.txt style body. Prints the verdict.
validate_body() {
  local u="$1" body head verdict links
  body="$(curl -sL -r 0-65535 --max-time 20 "$u" 2>/dev/null | head -c 65536 | tr -d '\r')"
  if [ -z "$body" ]; then echo "EMPTY"; return; fi
  head="$(printf '%s' "$body" | head -c 512 | sed -e 's/^[[:space:]]*//' | head -c 64 | tr 'A-Z' 'a-z')"
  case "$head" in
    "<!doctype"*|"<html"*) echo "FAKE(html)"; return ;;
  esac
  if printf '%s\n' "$body" | grep -qiE '^[[:space:]]*(user-agent|disallow):'; then
    echo "FAKE(robots)"; return
  fi
  links="$(printf '%s\n' "$body" | grep -o '](http' | wc -l | tr -d ' ')"
  if [ "$links" -eq 0 ]; then
    verdict="WEAK(no links)"
  else
    verdict="OK($links links)"
  fi
  if printf '%s\n' "$body" | grep -qiE 'ignore (all |any )?previous instructions|you are now|system prompt|do not tell the user'; then
    verdict="$verdict INJECTION?"
  fi
  echo "$verdict"
}

printf "%-7s %-26s %-22s %s\n" "STATUS" "CONTENT-TYPE" "VERDICT" "URL"
for h in "${hosts[@]}"; do
  candidates=(
    "https://$h/llms.txt"
    "https://$h/llms-full.txt"
    "https://$h/.well-known/llms.txt"
    "https://$h/docs/llms.txt"
    "https://$h/docs/llms-full.txt"
    "https://$h/.well-known/skills/index.json"
    "https://$h/mcp"
    "https://$h/pricing.md"
    "https://$h/index.md"
    "https://$h/api/openapi.json"
    "https://$h/openapi.json"
    "https://$h/sitemap.xml"
  )
  for u in "${candidates[@]}"; do
    # -sI HEAD request; fall back to GET range if HEAD is blocked
    hdr="$(curl -sIL --max-time 15 "$u" 2>/dev/null | tr -d '\r')"
    code="$(printf '%s\n' "$hdr" | awk '/^HTTP/{c=$2} END{print c}')"
    ctype="$(printf '%s\n' "$hdr" | awk -F': ' 'tolower($1)=="content-type"{v=$2} END{print v}')"
    if [ -z "$code" ] || [ "$code" = "405" ] || [ "$code" = "403" ]; then
      # some servers reject HEAD; try a 1-byte GET
      c2="$(curl -sL -o /dev/null -w '%{http_code}' -r 0-0 --max-time 15 "$u" 2>/dev/null)"
      if [ -n "$c2" ] && [ "$c2" != "000" ]; then code="$c2"; ctype="(GET)"; fi
    fi
    verdict="-"
    case "$u" in
      */llms.txt|*/llms-full.txt)
        case "$code" in 2*) verdict="$(validate_body "$u")" ;; esac ;;
      */mcp)
        # an HTML 200 is the docs site's catch-all page, not an MCP endpoint;
        # 401 means an auth-gated MCP server
        case "$code" in
          200) case "$ctype" in *html*) ;; *) verdict="exists?" ;; esac ;;
          400|401|405|406) verdict="exists?" ;;
        esac ;;
    esac
    printf "%-7s %-26s %-22s %s\n" "${code:-ERR}" "${ctype:0:26}" "${verdict:0:22}" "$u"
  done
done

first="${hosts[0]}"
echo
echo "tip: for any HTML doc page, also try appending .md (e.g. https://$first/some/page.md)"
echo "tip: found a skills index? \`npx skills add https://<host>\` installs the vendor-written skill; read it before trusting it."
