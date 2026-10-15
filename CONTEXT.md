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

**Name**:
The Name Part saying what the item is; kept from the current name unless a new one is typed for a single item, and always shaped by the Style.
_Avoid_: title, base name

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
