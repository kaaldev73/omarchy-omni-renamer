# OmniRename for Omarchy

OmniRename gives the files and folders you select in Omarchy's Nautilus file
manager consistent names. Press `Alt+S`, choose a Style, optionally add a Date,
Version or Initials, and every selected item is renamed in one go. If you change
your mind, any earlier name can be restored.

Outside Nautilus, `Alt+S` goes to the focused application unchanged, and `F2`
keeps its normal behaviour everywhere.

## Features

- Files and folders in one batch
- Eight Styles: kebab-case, snake_case, PascalCase, camelCase, UPPERCASE,
  lowercase, Title Case and Sentence case
- Names built as Date, Name, Version, Initials; parts already in a name are
  recognised and kept
- A Version without a number bumps the existing one, or starts at `v1`
- All selected items are renamed together or none are; nothing is ever
  overwritten
- A persistent History of every item's earlier names, with one-click restore
- Colours from the current Omarchy theme, read each time the window opens

## Install

```bash
omarchy plugin add https://github.com/kaaldev73/Omarchy_OmniRename.git --enable
~/.config/omarchy/plugins/io.github.omnirename.omarchy/install-omarchy.sh
```

The installer backs up `~/.config/hypr/bindings.lua` on first install, adds one
contextual `Alt+S` binding (replacing the `F2` one from earlier versions), adds
a window rule so the window floats centred, rescans the Omarchy shell, reloads
Hyprland, and checks for configuration errors. Its dependencies, `python` and
`wl-clipboard`, come with a standard Omarchy installation.

## Rename

1. Select one or more local files or folders in Nautilus.
2. Press `Alt+S`.
3. With one item selected, type a new Name if you want one. The grey text is
   the current Name, which is kept when the box is left empty. With several
   items the box is hidden and each keeps its own Name.
4. Choose a Style, then tick a Date, Version or Initials and adjust its value.
5. Press **Rename** (or `Enter`).

The result shows at the bottom of the window; **Show all** lists every item
when there are several. After a successful rename the window closes by itself
after 3 seconds, unless you press **Show all** or **Undo Rename** first.

If anything would go wrong, such as two items ending up with the same name, an
existing item in the way, or an invalid Date, nothing is renamed and the window
lists each Problem.

### Naming structure

```
DATE-NAME-VERSION-INITIALS.ext
```

Only the Name is always there; the Style shapes the Name and sets the separator.
The Version and Initials are never changed by the Style. `Project Report.pdf`
with a Date, Version 2 and Initials `KR` becomes:

| Style | Result |
|---|---|
| kebab-case | `20261015-project-report-v2-KR.pdf` |
| PascalCase | `20261015-ProjectReport-v2-KR.pdf` |
| snake_case | `20261015_project_report_v2_KR.pdf` |
| camelCase | `20261015-projectReport-v2-KR.pdf` |
| UPPERCASE | `20261015-PROJECT REPORT-v2-KR.pdf` |
| lowercase | `20261015-project report-v2-KR.pdf` |
| Title Case | `20261015-Project Report-v2-KR.pdf` |
| Sentence case | `20261015-Project report-v2-KR.pdf` |

The suggested folder rule is Sentence case for top-level folders
(`Client projects`) and kebab-case for everything inside them
(`project-report`).

## Undo

1. Select the renamed items in Nautilus and press `Alt+S`.
2. Press **Undo Rename** to see their History, newest name first.
3. With one item, click any earlier name to jump straight back to it.
   With several, **Undo last rename** steps each one back by one name.

Undo is all-or-nothing too: if any item's earlier name is taken, nothing is
restored. Items that were never renamed are skipped.

The History is kept in `~/.local/state/omnirename/rename_backlog.json`.

### Known limitations

- Items whose names were swapped in one rename (`a` → `b`, `b` → `a`) cannot be
  undone together; each earlier name counts as taken by the other item.
- If a folder and something inside it were both renamed, undoing them together
  restores the outer folder but silently skips the inner item, because the
  History still records the inner item under the folder's old path.

## Keys and icons

| Key | Action |
|---|---|
| `Enter` | Rename |
| `Escape` | Close the open page, or the window |
| `?` | How to rename and undo |

The question mark icon in the top right corner shows how to rename and undo.
The info icon shows the naming structure, an example in every Style, and the
folder rule. Click the icon again or press `Escape` to go back.

## Development

```bash
omarchy plugin validate .
```

| File | Role |
|---|---|
| `omni_care.py` | The window `Alt+S` opens |
| `name_parts.py` | Builds each new name from the Style and Name Parts |
| `omni_renamer.py` | Checks and carries out renames, with undo history |
| `omni_theme.py` | Turns the Omarchy theme into the window's colours |
| `omni_dispatch.py` | The contextual shortcut that opens the window in Nautilus |
| `Service.qml` | The do-nothing service the plugin manifest declares |

The domain language (Name Part, Style, Problem, …) is defined in
[`CONTEXT.md`](CONTEXT.md). The earlier QML overlay and theme experiments are
kept on the `prototype/*` branches.

### Trying it on mock folders

`mock/seed.py` creates folders with real rename history in `mock/folders/`,
covering multi-step renames, a swap, a nested folder, a blocked restore and an
item never renamed. Their History goes to `mock/state/`, so your own is
untouched:

```bash
python mock/seed.py
XDG_STATE_HOME=mock/state python omni_care.py mock/folders/chains/*
```

Run `python mock/seed.py` again to reset. Both generated folders are ignored by
git.

## Remove

Run `uninstall-omarchy.sh`, then:

```bash
omarchy plugin remove io.github.omnirename.omarchy
```
