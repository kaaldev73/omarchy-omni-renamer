#!/usr/bin/env bash
set -euo pipefail

plugin_id="io.github.omnirename.omarchy"
plugin_dir="$HOME/.config/omarchy/plugins/$plugin_id"
bindings="$HOME/.config/hypr/bindings.lua"
start_marker="-- OmniRename integration: start"
end_marker="-- OmniRename integration: end"

if [[ ! -f "$plugin_dir/manifest.json" ]]; then
  echo "Install this repository with 'omarchy plugin add <git-url> --enable' first." >&2
  exit 1
fi

# Replace any earlier OmniRename block, including the old F2 one, with the current one.
# The backup is taken once, so reinstalling never overwrites the pre-OmniRename bindings.
[[ -e "$bindings.omnirename-backup" ]] || cp "$bindings" "$bindings.omnirename-backup"
temporary="$(mktemp)"
awk '
  $0 == "-- OmniRename integration: start" || $0 == "-- OmniRename F2 integration: start" { skipping=1; next }
  $0 == "-- OmniRename integration: end" || $0 == "-- OmniRename F2 integration: end" { skipping=0; next }
  !skipping { print }
' "$bindings" > "$temporary"
{
  printf '%s\n' "$start_marker"
  printf '%s\n' '-- OmniRename opens on the Nautilus selection and forwards Alt+S everywhere else.'
  printf '%s\n' "o.bind(\"ALT + S\", \"OmniRename / forward Alt+S\", \"python $plugin_dir/omni_dispatch.py\")"
  printf '%s\n' 'o.window("^Omnirename$", { float = true, center = true })'
  printf '%s\n' "$end_marker"
} >> "$temporary"
install -m 0644 "$temporary" "$bindings"
rm -f "$temporary"

omarchy-shell shell rescanPlugins >/dev/null || true
omarchy plugin enable "$plugin_id" >/dev/null
hyprctl reload >/dev/null
errors="$(hyprctl configerrors)"
if [[ -n "$errors" ]]; then
  echo "$errors" >&2
  exit 1
fi

echo "OmniRename now opens with Alt+S in Nautilus and forwards Alt+S in other applications."
