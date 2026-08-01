"""Human approval records bound to an exact artifact checksum."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .download import sha256_file


def require_approval(path: Path, *, action: str, artifact_sha256: str) -> dict:
    if not path.is_file():
        raise PermissionError(f"Human approval record not found: {path}")
    approval = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema_version", "action", "approved", "reviewer", "approved_at", "artifact_sha256"}
    missing = required.difference(approval)
    if missing:
        raise PermissionError(f"Human approval record is missing: {', '.join(sorted(missing))}")
    if approval["schema_version"] != "1.0" or approval["action"] != action or approval["approved"] is not True:
        raise PermissionError(f"Human approval record does not approve {action}")
    if not str(approval["reviewer"]).strip():
        raise PermissionError("Human approval record requires a named reviewer")
    try:
        approved_at = datetime.fromisoformat(str(approval["approved_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PermissionError("Human approval record has an invalid approved_at timestamp") from exc
    if approved_at.tzinfo is None or approved_at.utcoffset() is None:
        raise PermissionError("Human approval record approved_at must include a UTC offset")
    if approval["artifact_sha256"] != artifact_sha256:
        raise PermissionError("Human approval record does not match the target artifact")
    return approval


def promote_approved_artifact(
    candidate_path: Path,
    production_path: Path,
    approval_file: Path,
    *,
    action: str,
) -> dict:
    """Atomically promote the exact candidate bytes covered by an approval."""
    candidate_sha256 = sha256_file(candidate_path)
    approval = require_approval(
        approval_file,
        action=action,
        artifact_sha256=candidate_sha256,
    )
    temporary = production_path.with_name(f"{production_path.name}.part")
    shutil.copyfile(candidate_path, temporary)
    if sha256_file(temporary) != candidate_sha256:
        temporary.unlink(missing_ok=True)
        raise OSError("Promoted artifact copy does not match the approved candidate")
    temporary.replace(production_path)
    return approval
