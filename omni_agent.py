"""Optional, privacy-bounded contextual filename recommendations."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from care_core import NamingOptions, transform_filename

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".toml", ".log",
    ".py", ".js", ".ts", ".html", ".css", ".xml",
}
MAX_EXCERPT = 6000


def summarize(path: Path, include_content: bool) -> dict:
    stat = path.stat()
    summary = {
        "source": str(path),
        "name": path.name,
        "kind": "folder" if path.is_dir() else "file",
        "mime": mimetypes.guess_type(path.name)[0] or "unknown",
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }
    if include_content and path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            summary["excerpt"] = path.read_text(encoding="utf-8", errors="replace")[:MAX_EXCERPT]
        except OSError:
            pass
    return summary


def baseline_recommendation(summary: dict) -> dict:
    path = Path(summary["source"])
    stem = path.stem
    excerpt = summary.get("excerpt", "")
    if excerpt:
        first = next((line.strip("# ") for line in excerpt.splitlines() if line.strip()), "")
        if 3 <= len(first) <= 80:
            stem = first
    extension = "" if summary["kind"] == "folder" else "".join(path.suffixes[-1:])
    candidate = transform_filename(stem + extension, NamingOptions("kebab-case"))
    return {
        "source": summary["source"],
        "suggested_name": candidate,
        "reason": "Derived from the first meaningful title and normalized for consistency",
        "confidence": 0.45,
    }


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer", "minimum": 0},
                        "suggested_name": {"type": "string"},
                        "reason": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["item_id", "suggested_name", "reason", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["recommendations"],
        "additionalProperties": False,
    }


def codex_recommendations(summaries: list[dict]) -> list[dict] | None:
    if not shutil.which("codex"):
        return None
    prompt = (
        "Recommend a concise, descriptive filename for every item in the supplied JSON. "
        "Preserve each file extension exactly. Never add directories, slashes, hidden-dot "
        "prefixes, or unsupported facts. Use kebab-case unless the content strongly requires "
        "another convention. Return only the required structured response.\n\n"
        + json.dumps(
            [
                {
                    "item_id": index,
                    **{key: value for key, value in item.items() if key != "source"},
                }
                for index, item in enumerate(summaries)
            ],
            ensure_ascii=False,
        )
    )
    with tempfile.TemporaryDirectory(prefix="omnirename-agent-") as directory:
        root = Path(directory)
        schema_path = root / "schema.json"
        output_path = root / "answer.json"
        schema_path.write_text(json.dumps(_schema()), encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    "codex", "exec", "--ephemeral", "--ignore-user-config",
                    "--skip-git-repo-check", "--sandbox", "read-only",
                    "--output-schema", str(schema_path), "--output-last-message",
                    str(output_path), "-",
                ],
                input=prompt,
                text=True,
                capture_output=True,
                cwd=root,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 or not output_path.exists():
            return None
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))["recommendations"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


def safe_recommendations(
    paths: list[Path], include_content: bool, allow_agent: bool = False
) -> dict:
    summaries = [summarize(path, include_content) for path in paths if path.exists()]
    baseline = [baseline_recommendation(summary) for summary in summaries]
    agent = codex_recommendations(summaries) if allow_agent else None
    if not agent or len(agent) != len(baseline):
        return {"provider": "local-baseline", "recommendations": baseline}
    validated = []
    by_id = {
        item.get("item_id"): item
        for item in agent
        if isinstance(item, dict) and isinstance(item.get("item_id"), int)
    }
    for index, fallback in enumerate(baseline):
        item = by_id.get(index, fallback)
        proposed = str(item.get("suggested_name", ""))
        source = Path(fallback["source"])
        extension_changed = source.is_file() and Path(proposed).suffix != source.suffix
        if (
            not proposed
            or Path(proposed).name != proposed
            or proposed.startswith(".")
            or any(ord(character) < 32 for character in proposed)
            or extension_changed
            or not isinstance(item.get("confidence", 0.5), (int, float))
        ):
            item = fallback
        else:
            item = {
                "source": fallback["source"],
                "suggested_name": proposed,
                "reason": str(item.get("reason", "Contextual recommendation")),
                "confidence": float(item.get("confidence", 0.5)),
            }
        validated.append(item)
    return {"provider": "codex", "recommendations": validated}
