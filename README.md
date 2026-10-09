# OmniRename for Omarchy

OmniRename replaces the normal `F2` rename flow in Omarchy's Nautilus file manager
with a theme-aware, preview-first batch renamer. Outside Nautilus, `F2` is
forwarded to the focused application unchanged.

The UI is a GTK window that `F2` opens on the current Nautilus selection. The
Omarchy plugin itself is a thin stub: it declares a do-nothing service so that
`omarchy plugin add` can install the files, and the install script adds the
`F2` binding.

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
- Native Omarchy theme colors
- Optional Codex-powered contextual filename Suggestions
- Metadata-only agent mode by default; text excerpts require explicit opt-in
- Local deterministic Suggestions when Codex is unavailable

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
2. Press `F2` to open the OmniRename window.
3. Type a base name and use backtick Commands to add a prefix, suffix, date or
   numbering, change the Style, or load a Preset. `` `? `` shows the cheat sheet.
4. Inspect every proposed result in the preview, then press `Enter` to rename.
5. Optionally use `` `22 `` for contextual name suggestions. They pass through the
   same Preview, and only a Safe Preview is renamed.
6. Reopen OmniRename on renamed items and use `` `u `` to restore their names.

### Command Mode key

Commands are typed while holding backtick; tapping it alone types a literal
backtick. If backtick is a dead key on your keyboard layout, choose another key
in `~/.config/OmniRename/settings.json` (or under `$XDG_CONFIG_HOME`):

```json
{ "command_key": "#" }
```

The value is the single character the key types. Choose a key typed without
Shift or AltGr (on German layouts `#` or `<`), since a held modifier changes the
digits typed in Commands, and not a dead key. It cannot be a letter, digit,
space or `?`, because those appear in Commands. A missing, unreadable or invalid
setting falls back to backtick. The cheat sheet (`?` Command) shows the key in use.

Suggestions in the window are local and deterministic; nothing is sent to an
agent. The optional Codex agent (`omni_agent.py`) runs ephemerally with a
read-only sandbox and a strict JSON response schema, shares only filenames and
basic metadata unless text excerpts are explicitly enabled, and is not wired
into the window.

## Development

```bash
python -m unittest discover -s tests -v
python care_cli.py preview '{"paths":["/tmp/Example File.txt"],"options":{"case_style":"kebab-case"}}'
omarchy plugin validate .
```

`care_core.py` is the safe rename engine and `care_cli.py` is the JSON bridge.
`omni_session.py` holds the Rename Session behind the window, and `omni_gtk.py` is
the GTK window that draws it. `care_f2.py` is the contextual shortcut adapter that
opens the window. `Service.qml` is the do-nothing service stub the plugin manifest
declares. The earlier QML overlay is kept on the `prototype/qml-overlay` branch.

## Remove

Run `uninstall-omarchy.sh`, then:

```bash
omarchy plugin remove io.github.omnirename.omarchy
```
