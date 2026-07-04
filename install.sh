#!/usr/bin/env bash
# Install the living-docs skills into Claude Code.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.claude/skills" "$HOME/.local/bin" "$HOME/.reach"
ln -sfn "$HERE/skills/docs"  "$HOME/.claude/skills/docs"
ln -sfn "$HERE/skills/reach" "$HOME/.claude/skills/reach"
ln -sf  "$HERE/skills/reach/scripts/reach" "$HOME/.local/bin/reach"
chmod +x "$HERE/skills/reach/scripts/reach" "$HERE/skills/docs/scripts/stale.py" "$HERE/skills/docs/scripts/probe_llmstxt.sh"
if [ ! -f "$HOME/.reach/keys.env" ]; then
  cp "$HERE/skills/reach/keys.env.example" "$HOME/.reach/keys.env"; chmod 600 "$HOME/.reach/keys.env"
fi
echo "Installed /docs + /reach skills. 'reach' is on ~/.local/bin (ensure it is on PATH)."
echo "Keys (optional): ~/.reach/keys.env   Library: ~/docs-reference (override with DOCS_REFERENCE_DIR)."
