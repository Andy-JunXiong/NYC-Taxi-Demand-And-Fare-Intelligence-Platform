import sqlite3
from pathlib import Path

import pytest

from nyc_taxi.operations import record_run


def test_run_ledger_records_success_and_failure(tmp_path: Path):
    ledger = tmp_path / "runs.sqlite"
    with record_run("sample", ledger=ledger) as state:
        state["gate_status"] = "passed"
        state["result"] = {"rows": 10}
    with pytest.raises(RuntimeError):
        with record_run("broken", ledger=ledger):
            raise RuntimeError("boom")
    connection = sqlite3.connect(ledger)
    rows = connection.execute(
        "SELECT pipeline,status,gate_status,error_message FROM pipeline_runs ORDER BY started_at"
    ).fetchall()
    connection.close()
    assert rows[0][:3] == ("sample", "completed", "passed")
    assert rows[1][0:2] == ("broken", "failed")
    assert "boom" in rows[1][3]
