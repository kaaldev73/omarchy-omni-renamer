#!/usr/bin/env bash
set -euo pipefail

plugin_id="io.github.omnirename.omarchy"
plugin_dir="$HOME/.config/omarchy/plugins/$plugin_id"
bindings="$HOME/.config/hypr/bindings.lua"
start_marker="-- OmniRename F2 integration: start"
end_marker="-- OmniRename F2 integration: end"

if [[ ! -f "$plugin_dir/manifest.json" ]]; then
  echo "Install this repository with 'omarchy plugin add <git-url> --enable' first." >&2
  exit 1
fi

if ! grep -Fq -- "$start_marker" "$bindings"; then
  cp "$bindings" "$bindings.care-backup"
  {
    printf '\n%s\n' "$start_marker"
    printf '%s\n' '-- F2 was previously handled directly by each application.'
    printf '%s\n' '-- OmniRename handles Nautilus selections and forwards F2 everywhere else.'
    printf '%s\n' "o.bind(\"F2\", \"OmniRename / forward F2\", \"python $plugin_dir/care_f2.py\")"
    printf '%s\n' "$end_marker"
  } >> "$bindings"
fi

omarchy-shell shell rescanPlugins >/dev/null || true
omarchy plugin enable "$plugin_id" >/dev/null
hyprctl reload >/dev/null
errors="$(hyprctl configerrors)"
if [[ -n "$errors" ]]; then
  echo "$errors" >&2
  exit 1
fi

echo "CaRe now handles F2 in Nautilus and forwards F2 in other applications."
