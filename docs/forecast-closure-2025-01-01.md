# First forecast-to-actual closure: 2025-01-01

## Outcome

The full 263-zone, 24-hour forecast was scored after January 2025 actuals arrived. The operational drift gate **failed**, so this run must not be presented as production-quality accuracy.

| Metric | Production forecast | Previous-week baseline |
|---|---:|---:|
| MAE | 7.48 | 7.65 |
| RMSE | 25.14 | 27.42 |
| WAPE | 52.34% | 53.52% |
| High-demand recall | 65.72% | 59.75% |

The model improved WAPE by only 2.2% relative to previous week, while under-predicting total demand by 31.5%. Airport WAPE was 30.04%; non-airport WAPE was 54.52%.

The largest failure occurred from midnight through 05:00 on New Year's Day. Actual demand was far above both the model and the previous-week pattern. This is an event/holiday generalization failure, not evidence that the monitoring code should relax its thresholds.

## Release response

The initial approved model artifact was retained immediately after this failure; it was not automatically retrained from one exceptional day. A later event-aware candidate added historical data and event treatment, then passed rolling tests that explicitly included New Year's Day and other major-event windows. Its release is documented in [`event-model-release-2025-01.md`](event-model-release-2025-01.md).

## January data-quality finding

January 2025 has a 4.15% negative `fare_amount` rate, above the 3% fare threshold. The issue is concentrated in Vendor 2 and payment types 0, 3, and 4. The current TLC dictionary defines payment type 0 as Flex Fare, and TLC added `cbd_congestion_fee` to 2025 trip data for the congestion-pricing charge.

Quality gates are therefore product-specific:

- Demand product: negative fare is a recorded warning because demand eligibility uses pickup time and Taxi Zone, not fare.
- Fare product: the same condition remains blocking until the new fare semantics are explicitly modeled.

Official references: [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) and [Yellow Taxi data dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf).

## Artifacts

- Gold now covers 2023-07 through 2025-01.
- The scored report is `data/processed/monitoring/forecast-performance.json`.
- January's gate report is `data/processed/quality/gate-report.json`.
- The original forecast remains unchanged and traceable through its lineage checksum.
