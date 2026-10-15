"""How a new name is built from its Name Parts: Date, Name, Version, Initials."""

import os
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Choices:
    """What to apply; None leaves a Name Part as it is, an empty version bumps it."""

    style: str = "kebab-case"
    date: str | None = None
    version: str | None = None
    initials: str | None = None


def to_kebab_case(name):
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[_\s]+', '-', name)
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', name)
    name = re.sub(r'([0-9])([a-zA-Z])', r'\1-\2', name)
    name = re.sub(r'([a-zA-Z])([0-9])', r'\1-\2', name)
    return name.lower()


def apply_style(name, style):
    if style == "kebab-case":
        return to_kebab_case(name)
    if style == "PascalCase":
        return ''.join(word.capitalize() for word in re.split(r'[_\s-]', name))
    if style == "snake_case":
        return to_kebab_case(name).replace("-", "_")
    if style == "camelCase":
        parts = to_kebab_case(name).split("-")
        return parts[0] + ''.join(word.capitalize() for word in parts[1:])
    if style == "UPPERCASE":
        return name.upper()
    if style == "lowercase":
        return name.lower()
    if style == "Title Case":
        return name.title()
    if style == "Sentence case":
        return name.capitalize()
    return name


DATE = re.compile(r'^(\d{8}|\d{6}|\d{4})(?=[-_\s])')
VERSION = re.compile(r'[-_\s][vV][-_]?(\d+)$')
INITIALS = re.compile(r'[-_\s]([A-Z]{2,3})$')
DATE_FORMATS = {8: "%Y%m%d", 6: "%Y%m", 4: "%Y"}


def is_real_date(digits):
    try:
        datetime.strptime(digits, DATE_FORMATS[len(digits)])
    except ValueError:
        return False
    return True


def split_name_parts(stem):
    """Recognise an existing Date, Version and Initials around the Name."""
    date = version = initials = None
    match = DATE.match(stem)
    if match and is_real_date(match.group(1)):
        date = match.group(1)
        stem = stem[match.end():].lstrip("-_ ")
    match = INITIALS.search(stem)
    if match:
        initials = match.group(1)
        stem = stem[:match.start()]
    match = VERSION.search(stem)
    if match:
        version = match.group(1)
        stem = stem[:match.start()]
    return date, stem, version, initials


def separator(style):
    return "_" if style == "snake_case" else "-"


def choice_problems(choices):
    """Problems with a typed Date or Version, which would otherwise end up in every name."""
    problems = []
    if choices.date and not (choices.date.isdigit() and len(choices.date) in DATE_FORMATS
                             and is_real_date(choices.date)):
        problems.append(f"Date {choices.date} is not a real yyyymmdd, yyyymm or yyyy date")
    version = (choices.version or "").strip().removeprefix("v").removeprefix("V")
    if choices.version and not version.isdigit():
        problems.append(f"Version {choices.version} is not a number")
    return problems


def split_extension(original_name):
    """Split off the extension, keeping a leading dot and .tar.* together."""
    hidden = "." if original_name.startswith(".") else ""
    stem, ext = os.path.splitext(original_name.removeprefix(hidden))
    if stem.lower().endswith(".tar"):
        stem, ext = stem[:-4], stem[-4:] + ext
    return hidden, stem, ext


def propose_name(original_name, choices):
    hidden, stem, ext = split_extension(original_name)
    date, name, version, initials = split_name_parts(stem)
    if choices.version == "":
        version = str(int(version) + 1) if version else "1"
    elif choices.version:
        version = choices.version.strip().removeprefix("v").removeprefix("V")
    parts = [
        choices.date or date,
        apply_style(name, choices.style),
        f"v{version}" if version else None,
        choices.initials or initials,
    ]
    return hidden + separator(choices.style).join(part for part in parts if part) + ext
