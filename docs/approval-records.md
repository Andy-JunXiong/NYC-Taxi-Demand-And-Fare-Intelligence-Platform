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

The template shape and inert defaults are checked by the test suite. Runtime
validation remains authoritative for a supplied record.
