#!/usr/bin/env bash
set -euo pipefail

bindings="$HOME/.config/hypr/bindings.lua"
temporary="$(mktemp)"
awk '
  $0 == "-- OmniRename F2 integration: start" { skipping=1; next }
  $0 == "-- OmniRename F2 integration: end" { skipping=0; next }
  !skipping { print }
' "$bindings" > "$temporary"
install -m 0644 "$temporary" "$bindings"
rm -f "$temporary"
hyprctl reload >/dev/null
hyprctl configerrors
echo "OmniRename F2 integration removed. The plugin can now be removed normally."
