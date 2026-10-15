# OmniRename

A batch renamer that takes over `F2` in Omarchy's file manager: it applies a Style, an optional prefix and suffix to the selected files and folders, and can undo the rename.

## Language

### Building a name

**Name Part**:
One section of a proposed filename: Prefix, Date, Name, Suffix, or Number.
_Avoid_: decoration, segment, field

**Pill**:
The on-screen form of a Name Part; a pill is shown exactly when its Name Part is in use.
_Avoid_: chip, tag

**Style**:
The rule for how words in the Name are separated and capitalised (kebab-case, snake_case, PascalCase, …).
_Avoid_: case, format

**Preset**:
A saved, named set of rules that restores every Name Part and Style at once.
_Avoid_: profile, template

**Suggestion**:
A proposed name per item that replaces the rules for that rename, offered by the agent and always shown in the Preview before use.
_Avoid_: recommendation, AI name

### Commands

**Command Mode**:
The state that lasts while the Command Mode key (backtick unless configured otherwise) is held down, like a modifier key; keys typed meanwhile form a Command instead of text, and releasing the key ends it.
_Avoid_: leader mode, magic mode

**Command**:
A short key code typed in Command Mode that acts on a Name Part, Style, Preset, or the rename itself.
_Avoid_: shortcut, sequence, magic key

### Safety

**Preview**:
The list of every selected item with its current name and the name it would receive.
_Avoid_: plan (in UI language), dry run

**Problem**:
A reason one item in the Preview cannot be renamed (duplicate result, existing target, invalid name, missing source).
_Avoid_: error, conflict, warning

**Safe Preview**:
A Preview with no Problems; only a Safe Preview can be renamed, and all items rename together or none do.
_Avoid_: valid plan
