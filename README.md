# OmniRename for Omarchy

OmniRename opens with `Alt+S` in Omarchy's Nautilus file manager and sets how
the names of the selected files and folders look. Outside Nautilus, `Alt+S` is
forwarded to the focused application unchanged, and `F2` keeps its normal
behaviour everywhere.

The UI is a tkinter window (`omni_care.py`, based on the earlier CaRe app) that
`Alt+S` opens on the current Nautilus selection. The Omarchy plugin itself is a
thin stub: it declares a do-nothing service so that `omarchy plugin add` can
install the files, and the install script adds the `Alt+S` binding.

## Features

- Files and folders in one batch
- kebab, snake, Pascal, camel, upper, lower, title, and sentence case
- Names built as Date, Name, Version, Initials; parts already in a name are kept
- A Version without a number bumps the existing one, or starts at `v1`
- All selected items rename together or none do; nothing is ever overwritten
- Persistent, atomic undo history
- Colours from the current Omarchy theme, read each time the window opens

## Install

```bash
omarchy plugin add https://github.com/kaaldev73/Omarchy_OmniRename.git --enable
~/.config/omarchy/plugins/io.github.omnirename.omarchy/install-omarchy.sh
```

The installer backs up `~/.config/hypr/bindings.lua` on first install, adds one
contextual `Alt+S` binding (replacing the `F2` one from earlier versions),
rescans the Omarchy shell, reloads Hyprland, and checks configuration errors.
Dependencies (`python` and `wl-clipboard`) are already present in a standard
Omarchy installation.

## Use

1. Select one or more local files or folders in Nautilus.
2. Press `Alt+S` to open the OmniRename window.
3. With one item selected, type a new Name if you want one (the grey text is
   the current Name, kept when the box is left empty; with several items each
   keeps its own Name and the box is hidden). Choose a Style, then tick a Date, Version or
   Initials and adjust its value.
4. Press **Rename**. **Undo Rename** restores the original names of the files
   the window was opened on. The result shows at the bottom of the window;
   **Show all** lists every item when there are several. After a successful
   rename the window closes by itself after 3 seconds, unless you use **Show
   all** or **Undo Rename** first. `Escape` closes the window.

Two icons sit in the top right corner: the question mark (or the `?` key) shows
how to rename and undo, and the info icon shows the naming structure, an
example in every Style, and the folder rule. Click the icon again or press
`Escape` to go back.

The rename history is kept in `~/.local/state/omnirename/rename_backlog.json`.
The window floats centred thanks to a Hyprland window rule the installer adds.

## Development

```bash
python -m unittest discover -s tests -p "test_*.py" -v
omarchy plugin validate .
```

`omni_care.py` is the window `Alt+S` opens, `name_parts.py` builds each new
name, and `omni_renamer.py` checks and carries out the renames with undo history.
`omni_theme.py` turns the Omarchy theme into the window's colours, and
`omni_dispatch.py` is the contextual shortcut adapter that opens the window.
`Service.qml` is the do-nothing service stub the plugin manifest declares. The
earlier QML overlay and theme experiments are kept on the `prototype/*` branches.

## Remove

Run `uninstall-omarchy.sh`, then:

```bash
omarchy plugin remove io.github.omnirename.omarchy
```
