# Sydney Taxi Rank localisation

## Product boundary

The Sydney product is not a clone of the NYC trip-level platform. TfNSW publishes
static, real-time, and historical observations for selected monitored taxi ranks.
Historical observations have a 15-minute rank-and-class grain.

The official v2.0 specification defines three classes:

- `taxi`: numeric taxi counts;
- `wat`: numeric wheelchair-accessible taxi counts;
- `passenger`: ordinal `Low`, `Medium`, or `High` bands, not passenger counts.

Consequently, taxi/WAT arrivals are regression targets while passenger demand is
an ordinal classification target. Passenger bands must never be summed or presented
as trip totals.

## Governance design

```text
TfNSW API JSON
    -> credential-safe immutable Bronze capture
    -> sydney_taxi_rank.v1 contract
    -> row-preserving Silver with UTC and Australia/Sydney timestamps
    -> quality report and checksums
    -> separate taxi-arrival and passenger-band Gold products
```

The contract is stored at `contracts/sydney_taxi_rank.v1.json`. NYC and Sydney
records remain separate through Silver. A future cross-city semantic layer may
compare interval demand states, but must not pretend that passenger bands and NYC
pickup counts are the same measure.

## Source caveats

- Coverage is limited to selected CCTV-equipped and secure ranks, not every taxi
  trip or rank in Sydney.
- TfNSW states that outsourced systems provide the data and may be reset after
  power or operational failures.
- Real-time observations may be delayed by 40-50 seconds.
- The real-time API restarts at 4am daily, causing a short availability gap.
- API specifications may change as coverage expands.
- Taxi Rank Locations CSV is historical and explicitly includes decommissioned
  ranks and omits some newer ranks; the API static feed should be authoritative for
  monitored ranks.

## Local configuration

Register or sign in to the TfNSW Open Data Hub, open the Taxi Ranks API resource,
and copy the authenticated endpoint values into a local `.env` or shell environment:

```text
TFNSW_API_KEY=...
TFNSW_AUTH_HEADER=Authorization
TFNSW_AUTH_SCHEME=apikey
TFNSW_TAXI_RANK_STATIC_URL=https://api.transport.nsw.gov.au/v1/taxirank/info
TFNSW_TAXI_RANK_REALTIME_URL=https://api.transport.nsw.gov.au/v1/taxirank/realtime
TFNSW_TAXI_RANK_HISTORICAL_URL_TEMPLATE=https://api.transport.nsw.gov.au/v1/taxirank/history?rankId={rank_id}&date={date}
```

The endpoints above are defined by the official Taxi Rank Swagger v1 specification.
Do not paste a key into source code, chat, screenshots, or committed files.

## Commands

```bash
python -m src.sydney_taxi.capture static
python -m src.sydney_taxi.capture realtime
python -m src.sydney_taxi.capture historical --rank-id P2P0003 --date 2024-06-25
python -m src.sydney_taxi.governance
```

The capture command stores the unmodified JSON response and appends its checksum to
the raw manifest. The governance command validates the documented root and fields,
normalizes missing tokens, preserves raw measures, adds typed class-specific fields,
converts UTC to `Australia/Sydney`, adds `dq_*` flags, and reconciles row counts.

## Next release gate

Before building a Sydney forecast, capture and inspect:

1. one static response;
2. one real-time response;
3. at least two historical responses for different ranks and dates.

These samples confirm authenticated endpoint syntax and whether production values
match the v2.0 examples. Only then should historical backfill automation and Gold
model tables be enabled.
