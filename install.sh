#!/usr/bin/env bash
# Install the living-docs skills into Claude Code.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.claude/skills" "$HOME/.local/bin" "$HOME/.reach"
# ln -sfn into an existing real directory would drop the link INSIDE it
# (skills/docs/docs) and leave the old copy active, so back that copy up first.
link_skill() {
  local src="$1" dst="$2"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    # outside ~/.claude/skills, or Claude Code would load the backup as a second skill
    local bak="$HOME/.claude/skills-backup/$(basename "$dst")-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$HOME/.claude/skills-backup"
    mv "$dst" "$bak"
    echo "Existing $dst moved to $bak (it was a real directory, not a link)."
  fi
  ln -sfn "$src" "$dst"
}
link_skill "$HERE/skills/docs"  "$HOME/.claude/skills/docs"
link_skill "$HERE/skills/reach" "$HOME/.claude/skills/reach"
ln -sf  "$HERE/skills/reach/scripts/reach" "$HOME/.local/bin/reach"
chmod +x "$HERE/skills/reach/scripts/reach" "$HERE"/skills/docs/scripts/*.py "$HERE/skills/docs/scripts/probe_llmstxt.sh"
ln -sf "$HERE/skills/docs/scripts/search.py" "$HOME/.local/bin/docs-search"
if [ ! -f "$HOME/.reach/keys.env" ]; then
  cp "$HERE/skills/reach/keys.env.example" "$HOME/.reach/keys.env"; chmod 600 "$HOME/.reach/keys.env"
fi
echo "Installed /docs + /reach skills. 'reach' and 'docs-search' are in ~/.local/bin (ensure it is on PATH)."
echo "Keys (optional): ~/.reach/keys.env   Library: ~/docs-reference (override with DOCS_REFERENCE_DIR)."
