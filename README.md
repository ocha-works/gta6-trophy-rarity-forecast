# gta6-trophy-rarity-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/ocha-works/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/ocha-works/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A forecasting program for Grand Theft Auto VI's trophy earn rates on Exophase. Given a case file holding every read the house recorded of the game's PS5 trophy page before a checkpoint, it writes five quantiles (0.05–0.95) of each trophy's earn rate at the case's target — for the final, the rates at 2026-11-26 00:00 UTC, four and a half days after the last read it may see. The contest scores pinball loss on the logit scale, so the model works there: per trophy, a recency-weighted trend of the logit rate on a decelerating launch clock, shrunk toward persistence and anchored at the last read, with a spread that combines a horizon term, the trophy's residual scale around its fit and the RMS of its read-to-read steps (an Exophase refresh moves a rate in one step, not gradually). See MODEL.md for the model and its validation.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only. `input/` is a directory of case files (`*.in`, e.g. the practice cases from the competition kit); one `<id>.out` forecast is written per case. With no environment variables set it reads `/input` and writes `/output`, as the grader runs it. The program is deterministic: two runs on the same case write the same bytes.

---

<sub>Entered on [make.fun](https://make.fun/?ref=yhjp53pb&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
