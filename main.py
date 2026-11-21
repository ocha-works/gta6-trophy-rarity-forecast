"""Forecast GTA VI trophy earn rates at a case's target (make.fun gta6-trophy-rarity-forecast-01).

The model, per trophy, works on the logit scale, because the contest scores pinball
loss there: a move from 1% to 2% costs about what a move from 33% to 50% costs.

Median: the trophy's logit rate is regressed, by recency-weighted least squares,
on ln(1 + hours since 2026-11-19T00:00Z) — a clock on which launch-week growth
decelerates. The fitted slope is shrunk toward zero (noisy short histories earn
little trend) and the forecast is anchored at the last observed logit, so the
median is last_logit + shrunk_slope * (x_target - x_last), with the total move
capped. Anchoring at the last read keeps a step change (an Exophase refresh)
inside the forecast instead of averaging it away.

Spread: a horizon term (a floor for refresh jumps, growing like sqrt of the
horizon in days) combined with the trophy's own weighted residual scale around
its fit and the RMS of its read-to-read logit steps, so a trophy whose recorded
path jumps (a refresh moves a rate in one step) gets a wider band than one that
glides. Quantiles are the normal quantiles at the case's levels.

Deterministic: pure arithmetic on the input file, no randomness, no clock, no
network. Python 3.13, standard library only.

Run: python3 main.py with MAKEFUN_INPUT_DIR / MAKEFUN_OUTPUT_DIR set, or
/input and /output when they are not.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]

# The clock the trend is fitted on: hours since the start of release day (UTC).
EPOCH = datetime(2026, 11, 19, 0, 0, 0, tzinfo=timezone.utc).timestamp()

HALF_LIFE_HOURS = 18.0   # recency weighting of reads in the trend fit
SHRINK_N = 5.0           # effective reads at which the slope is half trusted
SLOPE_CAP = 1.5          # max |slope|, logit per unit of ln(1 + hours)
MOVE_CAP = 2.2           # max |median move| from the last logit, in logits
SPREAD_FLOOR = 0.30      # logit spread even at a zero horizon (a refresh can land any time)
SPREAD_PER_SQRT_DAY = 0.45
RESID_WEIGHT = 0.6       # how much of the residual scale the horizon buys
STEP_WEIGHT = 0.5        # how much of the step scale the horizon buys
SIGMA_MIN = 0.35
SIGMA_MAX = 2.4


def clamp_rate(pct: float) -> float:
    return min(99.99, max(0.01, pct))


def logit(pct: float) -> float:
    p = clamp_rate(pct)
    return math.log(p / (100.0 - p))


def inv_logit(y: float) -> float:
    if y >= 0:
        return 100.0 / (1.0 + math.exp(-y))
    e = math.exp(y)
    return 100.0 * e / (1.0 + e)


def round4(x: float):
    scaled = x * 10000.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000.0
    return int(value) if float(value).is_integer() else value


def parse_time(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def hours_since_epoch(ts: float) -> float:
    return (ts - EPOCH) / 3600.0


def x_of(ts: float) -> float:
    return math.log1p(max(0.0, hours_since_epoch(ts)))


def fit_trend(xs, ys, ws):
    """Weighted least squares y ~ a + b*x; returns (a, b, weighted residual sd, sum of weights)."""
    sw = sum(ws)
    if sw <= 0:
        return ys[-1], 0.0, 0.0, 0.0
    mx = sum(w * x for x, w in zip(xs, ws)) / sw
    my = sum(w * y for y, w in zip(ys, ws)) / sw
    sxx = sum(w * (x - mx) ** 2 for x, w in zip(xs, ws))
    sxy = sum(w * (x - mx) * (y - my) for x, y, w in zip(xs, ys, ws))
    b = sxy / sxx if sxx > 1e-12 else 0.0
    a = my - b * mx
    var = sum(w * (y - (a + b * x)) ** 2 for x, y, w in zip(xs, ys, ws)) / sw
    return a, b, math.sqrt(max(0.0, var)), sw


def step_scale(points):
    """RMS of the trophy's read-to-read logit steps, each normalised to a per-day
    rate: how jumpy this trophy's recorded path is (an Exophase refresh moves a
    rate in one step, not gradually). 0.0 when there are no usable steps."""
    total = 0.0
    count = 0
    for (x0, y0, _w0, h0), (x1, y1, _w1, h1) in zip(points, points[1:]):
        gap_days = (h1 - h0) / 24.0
        if gap_days <= 0:
            continue
        step = (y1 - y0) / math.sqrt(gap_days)
        total += step * step
        count += 1
    if count == 0:
        return 0.0
    return min(1.2, math.sqrt(total / count))


def forecast_trophy(points, x_last_read, x_target, horizon_days):
    """points: list of (x, logit_rate, weight, hours) in read order.
    Returns (median_logit, sigma)."""
    if not points:
        return logit(0.01), SPREAD_FLOOR + SPREAD_PER_SQRT_DAY * math.sqrt(horizon_days)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ws = [p[2] for p in points]
    last_logit = ys[-1]
    if len(points) < 3:
        sigma = SPREAD_FLOOR + SPREAD_PER_SQRT_DAY * math.sqrt(horizon_days)
        return last_logit, min(SIGMA_MAX, max(SIGMA_MIN, sigma))
    a, b, resid_sd, n_eff = fit_trend(xs, ys, ws)
    shrink = n_eff / (n_eff + SHRINK_N)
    slope = max(-SLOPE_CAP, min(SLOPE_CAP, b * shrink))
    move = slope * (x_target - x_last_read)
    move = max(-MOVE_CAP, min(MOVE_CAP, move))
    median = last_logit + move
    resid_sd = min(1.0, max(0.10, resid_sd))
    step_sd = step_scale(points)
    base = SPREAD_FLOOR + SPREAD_PER_SQRT_DAY * math.sqrt(horizon_days)
    horizon_buy = min(horizon_days, 2.0)
    sigma = math.sqrt(
        base * base
        + (resid_sd ** 2) * horizon_buy * RESID_WEIGHT
        + (step_sd ** 2) * horizon_buy * STEP_WEIGHT
    )
    return median, min(SIGMA_MAX, max(SIGMA_MIN, sigma))


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    history = case["history"]
    if not history:
        raise ValueError(f"{name} has no history")
    read_ts = [parse_time(read["at"]) for read in history]
    last_ts = read_ts[-1]
    target_ts = parse_time(case["target"])
    horizon_days = case["horizon_minutes"] / 1440.0
    x_target = x_of(target_ts)
    x_last_read = x_of(last_ts)
    rows = []
    for i, trophy in enumerate(case["trophies"]):
        points = []
        for read, ts in zip(history, read_ts):
            rate = read["rates"][i]
            if rate is None:
                continue
            age_hours = (last_ts - ts) / 3600.0
            weight = 0.5 ** (age_hours / HALF_LIFE_HOURS)
            points.append((x_of(ts), logit(rate), weight, hours_since_epoch(ts)))
        median, sigma = forecast_trophy(points, x_last_read, x_target, horizon_days)
        qs = []
        prev = 0.0
        for z in Z:
            q = round4(inv_logit(median + z * sigma))
            q = max(prev, min(100.0, float(q)))
            qs.append(q)
            prev = q
        rows.append({"id": trophy["id"], "q": qs})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
