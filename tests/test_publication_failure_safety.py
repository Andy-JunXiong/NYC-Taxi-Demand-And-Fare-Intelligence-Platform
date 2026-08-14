import json
import subprocess
import sys
from pathlib import Path

PROBE = Path(__file__).with_name("publication_failure_probe.py")


def test_publication_failures_preserve_previous_consistent_set():
    completed = subprocess.run(
        [sys.executable, str(PROBE)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    result = json.loads(completed.stdout)
    assert result["status"] == "safe_failure_behavior_observed"
    assert [scenario["failure_point"] for scenario in result["scenarios"]] == [
        "lineage_write",
        "latest_write",
        "latest_replace",
    ]
    assert all(scenario["safe_failure"] for scenario in result["scenarios"])
