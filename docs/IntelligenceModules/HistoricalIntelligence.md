# Historical Intelligence

## Purpose and Version 0.2 scope

Historical Intelligence explains how a prepared collection snapshot changed
from its immediately preceding snapshot. It supports research only and never
recommends buying, selling or keeping a release.

The first vertical slice compares exactly two snapshots. It does not provide
custom ranges, arbitrary selection, charts, time-series aggregation,
forecasting or persisted intelligence results.

## Architecture

`HistoricalIntelligenceModule` implements the shared `IntelligenceModule`
contract, consumes only `IntelligenceContext.history`, and returns a standard
`IntelligenceResult`. It performs no SQLite, Discogs, dashboard or desktop
calls. The Version 0.2 registry exposes it after Collection Health and Hidden
Gems without changing desktop behaviour.

Public output is structured as frozen dataclasses:

- `HistoricalSnapshotInfo` identifies each selected snapshot and its evidence
  coverage;
- `HistoricalReleaseIdentity` describes additions and removals;
- `HistoricalReleaseChange` explains a matched release's valuation movement;
- `HistoricalComparison` contains collection-size, valuation and ranked-change
  metrics.

## Snapshot selection

Each `IntelligenceContext.history` entry is one snapshot: its mapping key is
the snapshot/run identifier and its value is the prepared release sequence.

Selection is deterministic:

1. malformed snapshot containers are excluded;
2. a non-empty snapshot with no valid release records is excluded;
3. when every valid snapshot has a capture time, snapshots are ordered by
   `captured_at`, then identifier;
4. otherwise snapshots are ordered by identifier (numeric identifiers use
   numeric ordering);
5. the final two snapshots are the preceding and current snapshots.

Empty snapshot sequences are valid collection states. Identical timestamps
use the snapshot identifier as an explicit tie-breaker. Elapsed time is
reported only when both selected timestamps are valid.

## Release matching

Releases are matched by positive integer `release_id`, the stable identifier
in the current persistence model. Set differences identify additions and
removals. Only the intersection can produce value movements, so an addition
cannot become a gainer and a removal cannot become a decliner.

Rows without a valid identifier are excluded and diagnosed. If a snapshot
contains duplicate identifiers, the first record is retained and subsequent
records are disclosed and excluded. Rankings use absolute change magnitude,
then ascending release ID as the tie-breaker.

## Metric definitions

- Collection size: count of unique valid release identifiers.
- Collection-size change: current size minus previous size.
- Total estimated value: sum of usable release values.
- Average release value: total divided by release count.
- Median release value: middle value, or the mean of the two middle values.
- Absolute value change: current value minus previous value.
- Percentage change: `(current - previous) / previous × 100`.

The existing snapshot schema stores `lowest_price`, not a separate estimated
collection value. The default field priority is therefore `estimated_value`
when a prepared context supplies it, followed by `lowest_price` as the current
model's transparent valuation proxy. This is a marketplace listing value, not
a completed-sale valuation.

## Missing evidence

Missing or invalid values are never represented as zero. Aggregate total,
average, median and their changes are withheld when any release in that
snapshot lacks usable valuation evidence. Release movements remain available
for matched releases that have valid values in both snapshots. An empty
snapshot has a mathematical total of zero, while its average and median are
undefined.

A zero previous value is valid evidence for an absolute movement, but its
percentage change is unavailable. Diagnostics disclose malformed rows,
duplicates, partial coverage, excluded movements, unavailable elapsed time and
selection limitations.

## Configuration

The frozen `HistoricalIntelligenceConfig` validates:

- `maximum_gainers` and `maximum_decliners`;
- `minimum_absolute_value_change`;
- optional `minimum_percentage_change`;
- `value_decimal_places`;
- ordered `value_fields`.

Money calculations use `Decimal` and deterministic half-up rounding.

## Explainability and limitations

The result identifies both snapshots, states the ordering rule, provides the
calculation basis and valuation coverage, and gives each surfaced release its
old value, new value, absolute change, percentage change when valid, and plain
English evidence. No opaque overall score is produced.

Future evolution may add user-selected comparisons, longer time series,
currency-aware valuation and richer trend research. Version 0.2 deliberately
does not include recommendations, market-wide claims, forecasting, machine
learning, charts or presentation integration.
