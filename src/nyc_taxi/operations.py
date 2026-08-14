"""Persistent operational run ledger and recoverable workflow orchestration."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .approvals import promote_approved_artifact, require_approval
from .download import parse_month, sha256_file
from .model_validation import rolling_backtest
from .monitoring import LATEST_FORECAST_PATH, monitor, resolve_latest_forecast
from .monthly_pipeline import run_monthly
from .prediction import publish_forecast, write_forecast_candidate


LEDGER_PATH = Path("data/processed/operations/runs.sqlite")
PRODUCTION_MODEL_PATH = Path("models/demand_release/production.joblib")
MODEL_ARCHIVE_ROOT = Path("models/demand_release/archive")
STAGING_ROOT = Path("data/processed/staging")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_ledger(path: Path = LEDGER_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
          run_id TEXT PRIMARY KEY, pipeline TEXT NOT NULL,
          period_start TEXT, period_end TEXT, started_at TEXT NOT NULL,
          ended_at TEXT, status TEXT NOT NULL, gate_status TEXT,
          data_checksum TEXT, gold_checksum TEXT, model_checksum TEXT,
          forecast_checksum TEXT, result_json TEXT, error_message TEXT
        )
    """)
    connection.commit()
    return connection


@contextmanager
def record_run(pipeline: str, *, period_start: str | None = None, period_end: str | None = None, ledger: Path = LEDGER_PATH):
    run_id = str(uuid.uuid4())
    connection = connect_ledger(ledger)
    connection.execute(
        "INSERT INTO pipeline_runs(run_id,pipeline,period_start,period_end,started_at,status) VALUES(?,?,?,?,?,?)",
        (run_id, pipeline, period_start, period_end, _now(), "running"),
    )
    connection.commit()
    state: dict[str, object] = {"run_id": run_id}
    try:
        yield state
    except Exception as exc:
        connection.execute(
            "UPDATE pipeline_runs SET ended_at=?,status=?,error_message=?,result_json=? WHERE run_id=?",
            (_now(), "failed", f"{type(exc).__name__}: {exc}", json.dumps({"traceback": traceback.format_exc()}), run_id),
        )
        connection.commit()
        raise
    else:
        connection.execute(
            """UPDATE pipeline_runs SET ended_at=?,status=?,gate_status=?,data_checksum=?,gold_checksum=?,
               model_checksum=?,forecast_checksum=?,result_json=? WHERE run_id=?""",
            (_now(), state.get("status", "completed"), state.get("gate_status"), state.get("data_checksum"),
             state.get("gold_checksum"), state.get("model_checksum"), state.get("forecast_checksum"),
             json.dumps(state.get("result", {}), default=str), run_id),
        )
        connection.commit()
    finally:
        connection.close()


def validate_promotion_evidence(candidate_path: Path, report_path: Path) -> str:
    """Verify that a release-gate-passing report names the exact candidate."""
    if not candidate_path.is_file():
        raise PermissionError(f"Model candidate not found: {candidate_path}")
    if not report_path.is_file():
        raise PermissionError(f"Model release report not found: {report_path}")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PermissionError(f"Model release report is unreadable or invalid JSON: {report_path}") from exc
    if not isinstance(report, dict):
        raise PermissionError("Model release report must be a JSON object")
    if report.get("release_gate", {}).get("passed") is not True:
        raise PermissionError("Model release report does not contain a passing release gate")
    candidate_sha256 = sha256_file(candidate_path)
    promotion = report.get("promotion")
    if not isinstance(promotion, dict) or promotion.get("status") != "awaiting_human_approval":
        raise PermissionError("Model release report is not awaiting human approval")
    if promotion.get("candidate_sha256") != candidate_sha256:
        raise PermissionError("Model release report does not match the candidate artifact")
    return candidate_sha256


def archive_current_model(production_path: Path, archive_root: Path) -> tuple[str | None, Path | None]:
    """Atomically retain the exact current production bytes before replacement."""
    if not production_path.is_file():
        return None, None
    previous_sha256 = sha256_file(production_path)
    archive_path = archive_root / f"{previous_sha256}.joblib"
    if archive_path.exists():
        if not archive_path.is_file() or sha256_file(archive_path) != previous_sha256:
            raise OSError(f"Existing model archive does not match production: {archive_path}")
        return previous_sha256, archive_path
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive_path.with_name(f"{archive_path.name}.part")
    temporary.unlink(missing_ok=True)
    try:
        shutil.copyfile(production_path, temporary)
        if sha256_file(temporary) != previous_sha256:
            raise OSError("Archived model copy does not match current production")
        temporary.replace(archive_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return previous_sha256, archive_path


def promote_existing_candidate(
    candidate_path: Path,
    report_path: Path,
    approval_file: Path,
    *,
    production_path: Path,
    archive_root: Path,
) -> dict:
    """Promote one reviewed candidate while preserving the prior production bytes."""
    candidate_sha256 = validate_promotion_evidence(candidate_path, report_path)
    require_approval(
        approval_file,
        action="model_promotion",
        artifact_sha256=candidate_sha256,
    )
    previous_sha256, archive_path = archive_current_model(production_path, archive_root)
    if previous_sha256 is not None and sha256_file(production_path) != previous_sha256:
        raise OSError("Production model changed while it was being archived")
    production_path.parent.mkdir(parents=True, exist_ok=True)
    approval = promote_approved_artifact(
        candidate_path,
        production_path,
        approval_file,
        action="model_promotion",
    )
    production_sha256 = sha256_file(production_path)
    if production_sha256 != candidate_sha256:
        raise OSError("Production model does not match the approved candidate after promotion")
    return {
        "status": "promoted",
        "candidate_path": candidate_path.as_posix(),
        "report_path": report_path.as_posix(),
        "production_path": production_path.as_posix(),
        "candidate_sha256": candidate_sha256,
        "previous_model_sha256": previous_sha256,
        "production_model_sha256": production_sha256,
        "archive_path": archive_path.as_posix() if archive_path is not None else None,
        "reviewer": approval["reviewer"],
        "approved_at": approval["approved_at"],
    }


def require_staging_output(output_dir: Path, staging_root: Path | None = None) -> Path:
    """Reject candidate output paths outside the repository staging boundary."""
    staging_root = STAGING_ROOT if staging_root is None else staging_root
    resolved_output = output_dir.resolve()
    resolved_root = staging_root.resolve()
    try:
        relative = resolved_output.relative_to(resolved_root)
    except ValueError as exc:
        raise PermissionError(f"Forecast candidate output must be under {staging_root.as_posix()}") from exc
    if not relative.parts:
        raise PermissionError("Forecast candidate output must be a child directory of the staging root")
    return output_dir


def run_workflow(command: str, args) -> dict:
    with record_run(command, period_start=getattr(args, "start", None) and str(args.start)[:7], period_end=getattr(args, "end", None) and str(args.end)[:7], ledger=args.ledger) as state:
        if command == "monthly":
            result = run_monthly(args.start, args.end, force=args.force, skip_download=args.skip_download)
            state["gold_checksum"] = sha256_file(Path("data/processed/hourly_zone_demand.parquet"))
            state["gate_status"] = "passed"
        elif command == "model":
            result = rolling_backtest(
                Path("data/processed/hourly_zone_demand.parquet"),
                Path("models/demand_release"),
                first_test=args.first_test,
                max_iter=args.max_iter,
                approval_file=None,
            )
            state["gate_status"] = "passed" if result["release_gate"]["passed"] else "failed"
            if result["release_gate"]["passed"] and args.approval_file is not None:
                result = promote_existing_candidate(
                    Path("models/demand_release/candidate.joblib"),
                    Path("models/demand_release/rolling_backtest.json"),
                    args.approval_file,
                    production_path=PRODUCTION_MODEL_PATH,
                    archive_root=MODEL_ARCHIVE_ROOT,
                )
                state["model_checksum"] = result["production_model_sha256"]
            else:
                state["status"] = "blocked"
        elif command == "promote":
            result = promote_existing_candidate(
                args.candidate,
                args.report,
                args.approval_file,
                production_path=PRODUCTION_MODEL_PATH,
                archive_root=MODEL_ARCHIVE_ROOT,
            )
            state["gate_status"] = "passed"
            state["model_checksum"] = result["production_model_sha256"]
        elif command == "forecast":
            result = publish_forecast(
                Path("data/processed/hourly_zone_demand.parquet"), Path("models/demand_release/production.joblib"),
                Path("data/processed/forecasts/hourly_zone_demand_forecast.parquet"),
                Path("data/processed/lineage/hourly_zone_demand_forecast.json"),
                Path("data/processed/quality/forecast-gate.json"),
                horizon=args.horizon,
                approval_file=args.approval_file,
            )
            state["gate_status"] = "passed"
            state["forecast_checksum"] = result["output_sha256"]
        elif command == "forecast-candidate":
            output_dir = require_staging_output(args.output_dir)
            candidate_sha256 = validate_promotion_evidence(args.model, args.model_report)
            result = write_forecast_candidate(
                args.input,
                args.model,
                args.model_report,
                output_dir,
                horizon=args.horizon,
                expected_model_sha256=candidate_sha256,
            )
            state["gate_status"] = "passed"
            state["model_checksum"] = candidate_sha256
            state["forecast_checksum"] = result["output_sha256"]
        elif command == "monitor":
            if args.forecast is None:
                forecast_path, source_release = resolve_latest_forecast(args.latest)
                result = monitor(
                    forecast_path,
                    args.actual,
                    args.output,
                    source_release=source_release,
                )
            else:
                result = monitor(args.forecast, args.actual, args.output)
            state["gate_status"] = "waiting" if result["status"] == "waiting_for_actuals" else "passed" if result["drift"]["passed"] else "failed"
            if state["gate_status"] == "failed":
                state["status"] = "blocked"
        state["result"] = result
        return {"run_id": state["run_id"], **result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audited NYC Taxi operational workflows")
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    sub = parser.add_subparsers(dest="command", required=True)
    monthly = sub.add_parser("monthly")
    monthly.add_argument("--start", type=parse_month, required=True)
    monthly.add_argument("--end", type=parse_month, required=True)
    monthly.add_argument("--force", action="store_true")
    monthly.add_argument("--skip-download", action="store_true")
    model = sub.add_parser("model")
    model.add_argument("--first-test", default="2024-07")
    model.add_argument("--max-iter", type=int, default=60)
    model.add_argument("--approval-file", type=Path)
    promote = sub.add_parser("promote")
    promote.add_argument("--candidate", type=Path, required=True)
    promote.add_argument("--report", type=Path, required=True)
    promote.add_argument("--approval-file", type=Path, required=True)
    forecast = sub.add_parser("forecast")
    forecast.add_argument("--horizon", type=int, default=24)
    forecast.add_argument("--approval-file", type=Path, required=True)
    forecast_candidate = sub.add_parser("forecast-candidate")
    forecast_candidate.add_argument("--input", type=Path, required=True)
    forecast_candidate.add_argument("--model", type=Path, required=True)
    forecast_candidate.add_argument("--model-report", type=Path, required=True)
    forecast_candidate.add_argument("--output-dir", type=Path, required=True)
    forecast_candidate.add_argument("--horizon", type=int, default=24)
    monitor_parser = sub.add_parser("monitor")
    monitor_parser.add_argument("--forecast", type=Path)
    monitor_parser.add_argument("--latest", type=Path, default=LATEST_FORECAST_PATH)
    monitor_parser.add_argument("--actual", type=Path, default=Path("data/processed/hourly_zone_demand.parquet"))
    monitor_parser.add_argument("--output", type=Path, default=Path("data/processed/monitoring/forecast-performance.json"))
    args = parser.parse_args(argv)
    if hasattr(args, "horizon") and not 1 <= args.horizon <= 168:
        parser.error("horizon must be between 1 and 168 hours")
    result = run_workflow(args.command, args)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
