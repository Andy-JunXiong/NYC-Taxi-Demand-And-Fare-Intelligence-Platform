"""Resolve and verify immutable forecast releases through the canonical pointer."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .download import sha256_file


LATEST_SCHEMA_VERSION = "1.0"


def _resolve_bounded(base: Path, relative: str, *, parent: Path | None = None) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(f"Release pointer path must be relative: {relative}")
    resolved_base = base.resolve()
    resolved = (resolved_base / candidate).resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"Release pointer path escapes publication root: {relative}") from exc
    if parent is not None and resolved.parent != parent.resolve():
        raise ValueError(f"Release artifact is outside the declared bundle: {relative}")
    return resolved


def load_latest_release(latest_path: Path) -> dict:
    """Load the canonical pointer and verify its complete immutable bundle."""
    if not latest_path.is_file():
        raise FileNotFoundError(f"Forecast latest pointer not found: {latest_path}")
    try:
        pointer = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Forecast latest pointer is unreadable or invalid JSON: {latest_path}") from exc
    if not isinstance(pointer, dict):
        raise ValueError("Forecast latest pointer must be a JSON object")
    required = {
        "schema_version",
        "product",
        "release_id",
        "release",
        "forecast",
        "lineage",
        "gate",
        "output_sha256",
        "lineage_sha256",
        "gate_sha256",
        "generated_at",
        "forecast_start",
        "model_sha256",
    }
    missing = required.difference(pointer)
    if missing:
        raise ValueError(f"Forecast latest pointer is missing: {', '.join(sorted(missing))}")
    if pointer["schema_version"] != LATEST_SCHEMA_VERSION:
        raise ValueError("Forecast latest pointer has an unsupported schema version")
    if pointer["product"] != "hourly_zone_demand_forecast":
        raise ValueError("Forecast latest pointer names the wrong product")
    release_id = pointer["release_id"]
    if not isinstance(release_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", release_id):
        raise ValueError("Forecast latest pointer has an invalid release ID")
    for field in ("output_sha256", "lineage_sha256", "gate_sha256", "model_sha256"):
        digest = pointer[field]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Forecast latest pointer has an invalid {field}")

    base = latest_path.parent
    release_dir = _resolve_bounded(base, str(pointer["release"]))
    expected_release_parent = (base / "releases").resolve()
    if release_dir.parent != expected_release_parent or release_dir.name != release_id:
        raise ValueError("Forecast latest pointer names an invalid release directory")
    forecast_path = _resolve_bounded(base, str(pointer["forecast"]), parent=release_dir)
    lineage_path = _resolve_bounded(base, str(pointer["lineage"]), parent=release_dir)
    gate_path = _resolve_bounded(base, str(pointer["gate"]), parent=release_dir)
    if (
        forecast_path.name != "forecast.parquet"
        or lineage_path.name != "lineage.json"
        or gate_path.name != "gate.json"
    ):
        raise ValueError("Forecast latest pointer names unexpected release artifacts")
    artifacts = {
        "forecast": (forecast_path, pointer["output_sha256"]),
        "lineage": (lineage_path, pointer["lineage_sha256"]),
        "gate": (gate_path, pointer["gate_sha256"]),
    }
    for name, (path, expected_digest) in artifacts.items():
        if not path.is_file():
            raise FileNotFoundError(f"Forecast release {name} not found: {path}")
        if sha256_file(path) != expected_digest:
            raise ValueError(f"Forecast release {name} does not match latest pointer digest")

    try:
        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Forecast release lineage or gate is unreadable or invalid JSON") from exc
    if not isinstance(lineage, dict) or lineage.get("release_id") != release_id:
        raise ValueError("Forecast release lineage does not match latest pointer")
    if lineage.get("product") != pointer["product"] or lineage.get("status") != "published":
        raise ValueError("Forecast release lineage does not describe a published product")
    if lineage.get("output_sha256") != pointer["output_sha256"]:
        raise ValueError("Forecast release lineage names the wrong forecast digest")
    if not isinstance(gate, dict) or gate.get("passed") is not True:
        raise ValueError("Forecast release gate is missing or did not pass")
    if lineage.get("gate") != gate:
        raise ValueError("Forecast release lineage and gate artifact disagree")
    if (
        lineage.get("generated_at") != pointer["generated_at"]
        or lineage.get("forecast_start") != pointer["forecast_start"]
        or lineage.get("production_model_sha256") != pointer["model_sha256"]
    ):
        raise ValueError("Forecast release lineage metadata does not match latest pointer")
    return {
        **pointer,
        "latest_path": latest_path,
        "release_path": release_dir,
        "forecast_path": forecast_path,
        "lineage_path": lineage_path,
        "gate_path": gate_path,
        "lineage_record": lineage,
        "gate_record": gate,
    }
