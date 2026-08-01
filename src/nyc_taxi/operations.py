"""Persistent operational run ledger and recoverable workflow orchestration."""

from __future__ import annotations

import argparse
import json
import sqlite3
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .download import parse_month, sha256_file
from .model_validation import rolling_backtest
from .monitoring import monitor
from .monthly_pipeline import run_monthly
from .prediction import publish_forecast


LEDGER_PATH = Path("data/processed/operations/runs.sqlite")


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
                approval_file=args.approval_file,
            )
            state["gate_status"] = "passed" if result["release_gate"]["passed"] else "failed"
            if result["promotion"]["status"] == "promoted":
                state["model_checksum"] = sha256_file(Path("models/demand_release/production.joblib"))
            else:
                state["status"] = "blocked"
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
        elif command == "monitor":
            result = monitor(
                Path("data/processed/forecasts/hourly_zone_demand_forecast.parquet"),
                Path("data/processed/hourly_zone_demand.parquet"),
                Path("data/processed/monitoring/forecast-performance.json"),
            )
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
    forecast = sub.add_parser("forecast")
    forecast.add_argument("--horizon", type=int, default=24)
    forecast.add_argument("--approval-file", type=Path, required=True)
    sub.add_parser("monitor")
    args = parser.parse_args(argv)
    result = run_workflow(args.command, args)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
