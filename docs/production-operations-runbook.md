# Production operations runbook

## Forecast archive and latest release

Every successful forecast publication archives the previously published Parquet and lineage pair under:

```text
data/processed/forecasts/archive/
  forecast_date=YYYY-MM-DD/
    generated_at=YYYYMMDDTHHMMSSZ/
      forecast.parquet
      lineage.json
```

`data/processed/forecasts/latest.json` is the stable pointer to the current forecast, lineage, model checksum, output checksum, and generation time. A failed publication never changes the archive, current product, or latest pointer.

## Operational run ledger

All audited commands write to `data/processed/operations/runs.sqlite`, table `pipeline_runs`. Each row records the run ID, workflow, requested period, start/end time, status, gate state, Gold/model/forecast checksums, structured result, and any error.

Statuses are `running`, `completed`, `blocked`, or `failed`. A quality/model/drift gate can produce `blocked` without corrupting the last published product; an exception produces `failed` with its error and traceback.

```powershell
python -m src.nyc_taxi.operations monthly --start 2025-02 --end 2025-02
python -m src.nyc_taxi.operations model --first-test 2024-07 --max-iter 60
python -m src.nyc_taxi.operations promote --candidate <candidate.joblib> --report <rolling_backtest.json> --approval-file <path>
python -m src.nyc_taxi.operations forecast --horizon 24 --approval-file <path>
python -m src.nyc_taxi.operations monitor
```

Model validation without an approval writes `candidate.joblib` and stops before
production replacement. The separate `promote` command accepts an already
reviewed candidate, its release report, and an approval record. For compatibility
with the existing manual workflow, `model --approval-file <path>` first completes
model validation without promotion and then routes the resulting candidate
through the same guarded promotion path. The report must contain a passing
release gate, be in `awaiting_human_approval`, and name the exact candidate
SHA-256.

Promotion requires a JSON approval record with `schema_version: "1.0"`,
`action: "model_promotion"`, `approved: true`, a named `reviewer`, an ISO-8601
`approved_at` containing a UTC offset, and the candidate `artifact_sha256`;
pass its path using `--approval-file`. Promotion retains the exact previous
production model under
`models/demand_release/archive/<previous-sha256>.joblib`, then
atomically copies the exact approved candidate bytes into
`models/demand_release/production.joblib`. The ledger result records the prior
and new checksums plus the archive path.

The archive makes the previous bytes recoverable but does not authorize or
automate rollback. Replacing production with an archived model remains a
separate destructive operation requiring an authenticated-human instruction
naming the exact archive and production target.

Forecast publication requires a separate record with action
`forecast_publication` bound to the current production model SHA-256. Start from
the inert, checked
[`approval-record-template.json`](approval-record-template.json) and follow the
field guidance in [`approval-records.md`](approval-records.md).

### Approval record retention

Production approval records are retained under
`C:\ProgramData\NYCTaxi\approval-records\` using the pending, consumed, and
rejected lifecycle defined in [`approval-records.md`](approval-records.md). Run
production actions through `src.nyc_taxi.operations` so the final record can be
associated with its operational ledger `run_id`. After the command reaches a
final state, a named operator moves the unchanged record from `pending/` to the
matching `consumed/` or `rejected/` run directory. Archived records are not
reusable approvals.

The workflow-dispatch input is currently described as a repository-relative
path. Use of the approved checkout-external root through the self-hosted workflow
has not yet been verified. Do not use that dispatch path for model promotion or
forecast publication until a separately authorized verification confirms safe
path handling without executing a production write.

## Failure recovery

- Downloads retain `.part` files and resume with an HTTP Range request. A server that does not support Range causes a safe full-file restart.
- Existing raw and Silver partitions are skipped unless `--force` is supplied.
- Silver and Gold write to temporary files and replace published Parquet only after reconciliation succeeds.
- The monthly job derives the historical Gold range from lineage and checks every expected monthly quality report, preventing a one-month run from truncating historical Gold.
- Model promotion first retains the current production bytes in a checksum-keyed
  archive. The archive and production copy both use temporary writes and
  checksum verification before atomic replacement.
- Forecast production files use temporary writes and atomic replacement after
  their release gates pass.
- Forecast versions are immutable in the archive.

## Scheduling

`.github/workflows/operations.yml` provides monthly scheduled and manually dispatched production workflows. It intentionally targets a persistent self-hosted Windows runner labeled `nyc-taxi`; GitHub-hosted ephemeral runners do not retain the multi-gigabyte governed lake or production model between runs.

The scheduled run processes the previous month and executes model validation,
then stops at the human promotion checkpoint. Forecast publication and
monitoring are separately dispatched. Concurrency is limited to one production
workflow and running jobs are never cancelled by a newer trigger.

External setup required once: register the machine as a GitHub Actions self-hosted runner and add the `nyc-taxi` label. No API secret is required for public TLC downloads.

## CI sample

The ordinary CI workflow runs on GitHub-hosted Ubuntu with `data/sample/yellow_taxi_sample.parquet`. The end-to-end sample test validates the schema, creates a January Bronze subset and zone dimension, builds Silver, evaluates the demand gate, and publishes a temporary Gold product. CI never downloads the full lake or writes production artifacts.
