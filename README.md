# OmniRename for Omarchy

OmniRename replaces the normal `F2` rename flow in Omarchy's Nautilus file manager
with a theme-aware, preview-first batch renamer. Outside Nautilus, `F2` is
forwarded to the focused application unchanged.

## Features

- Live old/new-name preview
- Files and folders in one batch
- kebab, snake, Pascal, camel, upper, lower, title, and sentence case
- Plain or regular-expression find and replace
- Case-sensitive matching
- Date, custom prefix, and suffix decorations
- Person-name decoration before or after the base filename
- Named presets that restore a complete set of naming rules
- Configurable sequence start, step, padding, and position
- Left/right character trimming
- Duplicate, existing-target, invalid-name, and stale-preview checks
- Transactional staging with rollback diagnostics
- Persistent, atomic undo history
- Native Omarchy theme colors and overlay behavior
- Optional Codex-powered contextual filename recommendations
- Metadata-only agent mode by default; text excerpts require explicit opt-in
- Local deterministic recommendations when Codex is unavailable
- Editable agent recommendations that pass through the normal safety preview
- Category-based naming guide and hover explanations for advanced controls

## Install

```bash
omarchy plugin add https://github.com/YOUR-NAME/omnirename.git --enable
~/.config/omarchy/plugins/io.github.omnirename.omarchy/install-omarchy.sh
```

The installer backs up `~/.config/hypr/bindings.lua`, adds one contextual `F2`
binding, rescans the Omarchy shell, reloads Hyprland, and checks configuration
errors. Dependencies (`python`, `wtype`, and `wl-clipboard`) are already present
in a standard Omarchy installation.

## Use

1. Select one or more local files or folders in Nautilus.
2. Press `F2`.
3. Compose rename rules and inspect every proposed result.
   Save a named preset if you want to reuse the same rules later.
4. Select **Rename** when the preview is safe.
5. Optionally choose **Suggest with agent**. Review or edit every recommendation.
6. Reopen OmniRename on renamed items and select **Undo** to restore their names.

Agent recommendations are never applied automatically. Local suggestions are the
default. Filenames and basic metadata are supplied to Codex only when **Use Codex**
is explicitly checked before requesting suggestions.
File text is limited to a short excerpt and is included only when **Share text
excerpts** is checked. The agent runs ephemerally with a read-only sandbox and a
strict JSON response schema.

## Development

```bash
python -m unittest discover -s tests -v
python care_cli.py preview '{"paths":["/tmp/Example File.txt"],"options":{"case_style":"kebab-case"}}'
omarchy plugin validate .
```

`care_core.py` is the safe rename engine. `care_cli.py` is the JSON bridge,
`OmniRename.qml` is the Omarchy overlay, and `care_f2.py` is the contextual shortcut
adapter.

## Remove

Run `uninstall-omarchy.sh`, then:

```bash
omarchy plugin remove io.github.omnirename.omarchy
```
