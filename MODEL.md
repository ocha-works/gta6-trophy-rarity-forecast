# Model

## What is forecast

For each of the case's 55 trophies, five quantiles (0.05, 0.25, 0.5, 0.75, 0.95)
of its earn rate (percent of Exophase-tracked players holding it, as printed on
the game's trophy page) at the case's target. The score is mean pinball loss on
the logit scale, so every part of the model works in logit space.

## Median

- Clock: `x(t) = ln(1 + hours since 2026-11-19T00:00Z)`. Launch-week progress
  decelerates, and a line on this clock bends the right way.
- Per trophy, weighted least squares of `logit(rate)` on `x` over the case's
  reads, with recency weights halving every 18 hours.
- The slope is shrunk by `n_eff / (n_eff + 5)` (a short or flat history earns
  little trend), capped at ±1.5 logit per x-unit, and the forecast is anchored
  at the last observed logit: `median = last + slope * (x_target - x_last)`,
  with the total move capped at ±2.2 logits. Anchoring keeps a step change —
  an Exophase refresh, which moves every rate at once — inside the forecast
  instead of averaging it away, and the shrinkage keeps the model near the
  persistence baseline wherever the data has not earned a trend.

## Spread

`sigma` combines, in quadrature:

- a horizon term, `0.30 + 0.45 * sqrt(horizon_days)` — a floor that exists even
  at a 90-minute horizon, because a refresh can land at any time (on the
  practice cases the house baseline's band, `0.5 * sqrt(d)`, covered nothing
  once the first refresh arrived);
- the trophy's weighted residual sd around its own fit (floored 0.10, capped
  1.0), bought at `min(horizon_days, 2) * 0.6`;
- the RMS of the trophy's read-to-read logit steps, each normalised to a
  per-day rate (capped 1.2), bought at `min(horizon_days, 2) * 0.5` — a trophy
  whose recorded path jumps gets a wider band than one that glides.

`sigma` is clamped to [0.35, 2.4]. Quantiles are `inv_logit(median + z * sigma)`
at the standard normal quantiles of the five levels, rounded to 4 decimals
(half up), clamped to [0, 100] and made non-decreasing.

## Validation

- The practice cases (p00, p01) hold only the unchanged launch-night page, so
  no local score against their answers is possible; the program's outputs on
  them were checked for shape (55 rows, exact keys, monotone quantiles in
  [0, 100], 2,639 bytes), byte-identical output across two runs, and runtime
  (~0.14 s per case locally, against an 8 s limit).
- On a synthetic 100-read history (saturating earn curves per trophy plus a
  refresh dilution step, forecast 4.5 days out), the median's mean absolute
  logit error was 0.58 and the 5–95% band covered 55/55 trophies — the band
  is honest-to-wide on smooth data, which is the side pinball loss punishes
  less when a refresh is the alternative.

## Known weaknesses

- The trend is linear on the ln-hours clock; a trophy whose earners saturate
  hard (or whose rate is dominated by denominator growth late in the week)
  will bend away from the line, and only the spread covers that.
- Nothing in the model uses cross-trophy structure (tier, points, story
  order) or the players-tracked trajectory directly; both are visible in the
  residuals the per-trophy fit already absorbs, but a pooled model could
  sharpen the rarest trophies.
- The spread constants were set from the structure of the problem and the
  practice cases' one observed refresh, not fitted to scored outcomes; there
  was no scored history to fit them to.
