# Human approval records

Use [`approval-record-template.json`](approval-record-template.json) to create
one approval record for one exact action and artifact. The committed template
is intentionally inert: `approved` is `false` and its other values are
placeholders.

Before supplying a copied record to an operation, replace every placeholder and
set:

- `action` to either `model_promotion` or `forecast_publication`;
- `approved` to `true` only after the named reviewer makes that decision;
- `reviewer` to the reviewer's attributable name;
- `approved_at` to an ISO-8601 timestamp with a UTC offset; and
- `artifact_sha256` to the lowercase SHA-256 of the exact candidate model for
  promotion, or the exact production model for forecast publication.

Model promotion and forecast publication require separate records. An approval
for one action or digest cannot authorize another. Approval records must not
contain credentials, private data, generated models, or runtime outputs, and
creating a record does not itself run or authorize any other production action.

## Authoritative retention

The authoritative original approval record must be retained outside the
repository checkout under:

```text
C:\ProgramData\NYCTaxi\approval-records\
  pending\
    <record-id>.json
  consumed\
    YYYY\
      MM\
        <run-id>\
          approval.json
  rejected\
    YYYY\
      MM\
        <run-id>\
          approval.json
```

The authoritative original is the exact sequence of bytes supplied to the
operation. It must not be reformatted, overwritten, or replaced after approval.

For production operations:

1. A named human places the completed record in `pending/` before execution and
   makes it read-only.
2. The runner identity may read pending records but must not alter them. Named
   maintainers control creation, archival moves, and deletion through Windows
   filesystem permissions.
3. The audited `src.nyc_taxi.operations` entry point receives that exact file.
   After the ledger reaches a final state, the operator associates the record
   with the ledger `run_id` and moves the same bytes to `consumed/` for a
   completed operation or `rejected/` for a blocked or failed attempt.
4. A record under `consumed/` or `rejected/` must never be supplied to another
   production operation. This is an operational rule; current runtime code does
   not yet enforce one-time consumption.
5. Retain the record while any related model, forecast, archive, lineage, or
   ledger evidence is retained, and for any longer maintainer-approved audit
   period. Deletion requires an explicit maintainer decision.

Do not copy approval records into Git, generated model directories, forecast
products, logs, or workflow output. The approved storage root is an external
runner setup requirement; documenting it does not create the directory or grant
access to it.

The template shape and inert defaults are checked by the test suite. Runtime
validation remains authoritative for a supplied record.
