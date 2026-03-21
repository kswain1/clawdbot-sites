# Aura-V AutoResearch Program

## Your Job
Maximize `ev` (EV ratio) in `backtest_eval.py` by editing `strategy_params.py`.

## The Loop
1. Read `strategy_params.py` + `EXPERIMENT_LOG`
2. Propose ONE change to `PARAMS` with a hypothesis
3. Call `run_backtest(params)` from `backtest_eval.py` with new params
4. If new `ev` > best so far: update `PARAMS` and append to `EXPERIMENT_LOG`
5. Repeat — target: EV > 0.70 (Grade A)

## Current Best
EV +0.52, Grade A-, 80 trades, WR 40%, Net +$8,320

## Parameter Space
- `bb_period`: 10–50
- `bb_std`: 1.5–3.0
- `rr`: 1.5–5.0
- `htf_bars`: 12=1H, 24=2H, 48=4H, 96=8H
- `min_prob`: 0.10–0.50
- `entry_hours`: e.g. [8,9,10] NY-only, [18,19,20] Asia-only, [8,9,18,19,20] both

## Rules
- Change ONE param per experiment (isolate variables)
- After 5 single-param wins, try combinations
- Never delete EXPERIMENT_LOG entries
- If stuck 10 experiments, jump to a different param region

## Context
- XAUUSD, 5-min bars, 30-day backtest
- Risk=20pts, Contract=$10/pt, DailyCap=$400
- Bull rally Feb19–Mar11 was the killer — HTF filter already fixes counter-trend SELLs
- Push EV from +0.52 → +0.70+
