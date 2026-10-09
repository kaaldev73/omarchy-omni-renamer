"""JSON command interface between the OmniRename window and rename engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from care_core import NamingOptions, RenameError, RenameHistory, RenameTransaction, build_manual_plan, build_rename_plan
from care_presets import PresetStore


def options_from(data: dict) -> NamingOptions:
    counter = data.get("counter_start")
    return NamingOptions(
        case_style=str(data.get("case_style", "kebab-case")),
        name=str(data.get("name", "")),
        prefixes=tuple(filter(None, data.get("prefixes", []))),
        suffixes=tuple(filter(None, data.get("suffixes", []))),
        find=str(data.get("find", "")),
        replace=str(data.get("replace", "")),
        use_regex=bool(data.get("use_regex", False)),
        case_sensitive=bool(data.get("case_sensitive", False)),
        counter_start=int(counter) if counter is not None else None,
        counter_step=int(data.get("counter_step", 1)),
        counter_padding=int(data.get("counter_padding", 2)),
        counter_position=str(data.get("counter_position", "suffix")),
        trim_start=int(data.get("trim_start", 0)),
        trim_end=int(data.get("trim_end", 0)),
        person=str(data.get("person", "")),
        person_position=str(data.get("person_position", "suffix")),
    )


def item_json(item) -> dict:
    return {
        "source": str(item.source),
        "original": item.source.name,
        "destination": str(item.destination),
        "renamed": item.destination.name,
        "status": item.problem or ("ready" if item.changed else "unchanged"),
        "safe": not item.problem,
        "changed": item.changed,
    }


def execute(command: str, payload: dict) -> dict:
    if command == "list-presets":
        return {"ok": True, "names": PresetStore().names()}
    if command == "save-preset":
        PresetStore().save(str(payload.get("name", "")), payload.get("preset", {}))
        return {"ok": True, "names": PresetStore().names()}
    if command == "load-preset":
        return {"ok": True, "preset": PresetStore().load(str(payload.get("name", "")))}
    paths = [Path(value) for value in payload.get("paths", [])]
    transaction = RenameTransaction(RenameHistory())
    if command == "recommend":
        from omni_agent import safe_recommendations

        return {
            "ok": True,
            **safe_recommendations(
                paths,
                bool(payload.get("include_content", False)),
                bool(payload.get("allow_agent", False)),
            ),
        }
    if command == "undo":
        restored = transaction.undo(paths)
        return {"ok": True, "paths": [str(path) for path in restored]}
    if command in ("preview-manual", "apply-manual"):
        names = payload.get("names", [])
        if len(names) != len(paths):
            raise RenameError("Every selected item needs one proposed name.")
        if not all(isinstance(name, str) for name in names):
            raise RenameError("Every proposed name must be text.")
        plan = build_manual_plan(zip(paths, names))
    else:
        plan = build_rename_plan(paths, options_from(payload.get("options", {})))
    if command in ("preview", "preview-manual"):
        return {
            "ok": True,
            "safe": plan.is_safe,
            "changed": len(plan.changed_items),
            "items": [item_json(item) for item in plan.items],
        }
    if command in ("apply", "apply-manual"):
        renamed = transaction.apply(plan)
        return {"ok": True, "paths": [str(path) for path in renamed]}
    raise RenameError(f"Unknown command: {command}")


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"ok": False, "error": "Usage: care_cli.py COMMAND JSON"}))
        return 2
    try:
        result = execute(sys.argv[1], json.loads(sys.argv[2]))
    except (RenameError, ValueError, TypeError, json.JSONDecodeError) as error:
        result = {"ok": False, "error": str(error)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
