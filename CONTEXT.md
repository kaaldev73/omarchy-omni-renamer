# OmniRename

Opens with `Alt+S` in Omarchy's file manager and sets how the names of the selected files and folders look: first their Style, then optionally when the item is from, which version it is, and who made it.

## Language

### Building a name

**Name Part**:
One section of a new name, always in this order: Date, Name, Version, Initials. A Name Part already in a name is recognised and kept unless a new one is chosen to replace it.
_Avoid_: decoration, segment, field, prefix, suffix

**Date**:
The Name Part saying when the item is from, as yyyymmdd, yyyymm or yyyy; today unless changed, and at most one per name.
_Avoid_: timestamp

**Version**:
The Name Part saying which revision the item is, written `v` followed by a number (`v2`); asking for a Version without a number bumps the existing one, or starts at `v1`.
_Avoid_: revision number

**Initials**:
The Name Part saying who made the item, kept exactly as typed whatever the Style.
_Avoid_: author, signature

**Style**:
The rule for how words in the Name are separated and capitalised (kebab-case, snake_case, PascalCase, …); it shapes only the Name and sets the separator between Name Parts, never the Version or Initials themselves.
_Avoid_: case, format

### Safety

**Problem**:
A reason an item cannot be renamed (duplicate result, existing target, invalid name, missing source, a typed Date or Version that is not valid); any Problem stops the whole rename.
_Avoid_: error, conflict, warning

## GTK window (unused)

These terms describe the earlier GTK window, which stays in the repository but nothing opens. Delete them when that code goes.

**Pill**:
The on-screen form of a Name Part; a pill is shown exactly when its Name Part is in use.
_Avoid_: chip, tag

**Preset**:
A saved, named set of rules that restores every Name Part and Style at once.
_Avoid_: profile, template

**Suggestion**:
A proposed name per item that replaces the rules for that rename, offered by the agent and always shown in the Preview before use.
_Avoid_: recommendation, AI name

**Command Mode**:
The state that lasts while the Command Mode key (backtick unless configured otherwise) is held down, like a modifier key; keys typed meanwhile form a Command instead of text, and releasing the key ends it.
_Avoid_: leader mode, magic mode

**Command**:
A short key code typed in Command Mode that acts on a Name Part, Style, Preset, or the rename itself.
_Avoid_: shortcut, sequence, magic key

**Preview**:
The list of every selected item with its current name and the name it would receive.
_Avoid_: plan (in UI language), dry run

**Safe Preview**:
A Preview with no Problems; only a Safe Preview can be renamed, and all items rename together or none do.
_Avoid_: valid plan
