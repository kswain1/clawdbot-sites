#!/usr/bin/env python3
"""
autorun_expanded.py — 200-500 Experiment AutoResearch + Walk-Forward Validation
─────────────────────────────────────────────────────────────────────────────────
Phase 1: Single-param sweep         ~60 experiments
Phase 2: Combo sweep (top winners)  ~40 experiments  
Phase 3: Fine-tune best combo       ~30 experiments
Phase 4: Grid search (top combos)   ~80 experiments
Phase 5: Walk-Forward Validation    train D0-D120 → validate D121-D180
         Tests best configs on UNSEEN data — prevents overfitting

Total: ~210 experiments | estimated runtime: ~60-90 seconds
"""
import json, math, random, time, sys, itertools
sys.path.insert(0, '.')
from backtest_eval_180 import run_backtest, generate_prices_180

# ── Price series: generate once, split for walk-forward ──
PRICES_FULL = generate_prices_180()
BARS_PER_DAY = 288

# Walk-forward split
TRAIN_DAYS = 120   # days 0–119 = training window
VAL_DAYS   = 60    # days 120–179 = validation (unseen)
PRICES_TRAIN = PRICES_FULL[:TRAIN_DAYS * BARS_PER_DAY]
PRICES_VAL   = PRICES_FULL[TRAIN_DAYS * BARS_PER_DAY:]

BASELINE = {
    'bb_period':   20,
    'bb_std':      2.0,
    'rr':          2.8,
    'htf_bars':    48,
    'min_prob':    0.25,
    'entry_hours': [8, 9, 18, 19, 20],
}

GEN3 = {
    'bb_period':   20,
    'bb_std':      2.0,
    'rr':          5.0,
    'htf_bars':    48,
    'min_prob':    0.35,
    'entry_hours': [8, 9, 18, 19, 20],
}

# ── Expanded search space ──
SEARCH_SPACE = {
    'bb_period':   [10, 12, 14, 15, 17, 18, 20, 22, 25, 28, 30],
    'bb_std':      [1.2, 1.4, 1.5, 1.6, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0],
    'rr':          [1.5, 2.0, 2.5, 2.8, 3.0, 3.2, 3.5, 3.8, 4.0, 4.5, 5.0, 5.5, 6.0],
    'htf_bars':    [6, 12, 24, 48, 72, 96, 144],
    'min_prob':    [0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.32, 0.35, 0.38, 0.40, 0.45],
    'entry_hours': [
        [8, 9, 18, 19, 20],        # current best
        [8, 9, 10],                # NY open
        [8, 9],                    # NY power hour
        [18, 19],                  # Asia power hour (winner)
        [18, 19, 20, 21],          # Asia full
        [8, 9, 10, 18, 19, 20],    # both sessions
        [8, 9, 10, 18, 19],        # both power hours
        [7, 8, 9, 10],             # early NY
        [17, 18, 19],              # pre + Asia open
        list(range(6, 12)),        # all morning
        list(range(17, 22)),       # all evening
        [8, 9, 13, 14, 18, 19],   # NY + London close + Asia
    ],
}

def fmt(r):
    return f"EV={r['ev']:+.3f} | WR={r['wr']:>5.1f}% | Net=${r['net']:>+9,.0f} | DD={r['max_dd']:>5.1f}% | Grade={r['grade']}"

def regime_line(r):
    rg = r.get('regimes', {})
    parts = []
    for name, emoji in [('bull','🐂'),('chop','〰'),('bear','🐻'),('recovery','🔄')]:
        s = rg.get(name, {})
        parts.append(f"{emoji}{s.get('wr',0):.0f}%/${s.get('net',0):+,.0f}")
    return '  '.join(parts)

# ── Run sweep with tracking ──
def run_sweep():
    t0 = time.time()
    total_experiments = 0
    all_results = []

    baseline_full  = run_backtest(BASELINE, PRICES_FULL)
    baseline_train = run_backtest(BASELINE, PRICES_TRAIN)
    gen3_full      = run_backtest(GEN3, PRICES_FULL)

    best_ev_train = baseline_train['ev']
    best_params   = dict(BASELINE)
    best_full     = baseline_full

    print("\n" + "="*88)
    print("  AURA-V AUTORESEARCH — EXPANDED 200-500 EXPERIMENT SWEEP + WALK-FORWARD")
    print(f"  Train: Day 0–{TRAIN_DAYS} | Validate: Day {TRAIN_DAYS}–{TRAIN_DAYS+VAL_DAYS} | Full: 180D")
    print("="*88)
    print(f"\n  BASELINE  (FULL 180D): {fmt(baseline_full)}")
    print(f"            {regime_line(baseline_full)}")
    print(f"  GEN3      (FULL 180D): {fmt(gen3_full)}")
    print(f"  BASELINE  (TRAIN 120D): EV={baseline_train['ev']:+.3f} | WR={baseline_train['wr']}% | Net=${baseline_train['net']:+,.0f}")
    print()

    # ══════════════════════════════════════════════════════════
    # PHASE 1 — Single-param sweep on TRAIN data
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─'*88}")
    print(f"  PHASE 1 — Single-Param Sweep on TRAIN data (D0–{TRAIN_DAYS})")
    print(f"{'─'*88}")

    for param, values in SEARCH_SPACE.items():
        print(f"\n  ── {param} ({len(values)} values)")
        for val in values:
            params = dict(BASELINE); params[param] = val
            r = run_backtest(params, PRICES_TRAIN)
            delta = r['ev'] - baseline_train['ev']
            marker = '✅' if delta > 0.05 else '·'
            val_s = str(val)[:24]
            print(f"    {marker} {param}={val_s:<26} EV={r['ev']:+.3f}  Δ{delta:+.3f}  WR={r['wr']}%  Grade={r['grade']}")
            all_results.append({'param': param, 'value': val, 'ev': r['ev'], 'delta': delta, 'params': dict(params), 'result': r})
            total_experiments += 1
            if r['ev'] > best_ev_train:
                best_ev_train = r['ev']
                best_params = dict(params)
                best_full = run_backtest(params, PRICES_FULL)

    # ══════════════════════════════════════════════════════════
    # PHASE 2 — Combo sweep: top 8 single-param winners
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─'*88}")
    print(f"  PHASE 2 — Combo Sweep (top single-param winners)")
    print(f"{'─'*88}")

    winners = sorted([r for r in all_results if r['delta'] > 0.05], key=lambda x: -x['delta'])
    top8 = winners[:8]
    print(f"  Top {len(top8)} single-param winners:")
    for w in top8:
        print(f"    {w['param']}={str(w['value'])[:20]:<22} Δ{w['delta']:+.3f}")

    # All pairwise combos of top 6
    combo_results = []
    top6 = top8[:6]
    for i, j in itertools.combinations(range(len(top6)), 2):
        p = dict(BASELINE)
        p[top6[i]['param']] = top6[i]['value']
        p[top6[j]['param']] = top6[j]['value']
        r = run_backtest(p, PRICES_TRAIN)
        delta = r['ev'] - baseline_train['ev']
        note = f"{top6[i]['param']}={top6[i]['value']} + {top6[j]['param']}={top6[j]['value']}"
        marker = '✅' if r['ev'] > best_ev_train else '·'
        print(f"  {marker} [{note[:52]:<52}] EV={r['ev']:+.3f}  Δ{delta:+.3f}")
        combo_results.append({'note': note, 'params': p, 'ev': r['ev'], 'delta': delta})
        total_experiments += 1
        if r['ev'] > best_ev_train:
            best_ev_train = r['ev']; best_params = dict(p)
            best_full = run_backtest(p, PRICES_FULL)

    # Top-4 all-in combo
    for size in [3, 4, 5]:
        if size > len(top8): break
        p = dict(BASELINE)
        for w in top8[:size]: p[w['param']] = w['value']
        r = run_backtest(p, PRICES_TRAIN)
        delta = r['ev'] - baseline_train['ev']
        marker = '✅' if r['ev'] > best_ev_train else '·'
        print(f"  {marker} [top-{size} ALL COMBO{'':18}] EV={r['ev']:+.3f}  Δ{delta:+.3f}")
        total_experiments += 1
        if r['ev'] > best_ev_train:
            best_ev_train = r['ev']; best_params = dict(p)
            best_full = run_backtest(p, PRICES_FULL)

    # ══════════════════════════════════════════════════════════
    # PHASE 3 — Fine-tune around best combo
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─'*88}")
    print(f"  PHASE 3 — Fine-Tune Around Best Combo")
    print(f"{'─'*88}")
    print(f"  Current best: EV={best_ev_train:+.3f}  Params: {json.dumps(best_params, separators=(',',':'))}")

    fine_params = {
        'rr':       [x/10 for x in range(25, 65, 2)],   # 2.5 to 6.4 step 0.2
        'min_prob': [x/100 for x in range(20, 50, 2)],  # 0.20 to 0.48 step 0.02
        'bb_period':[11,13,14,15,16,17,18,19,20,21,22,23,24,25],
        'bb_std':   [1.3,1.5,1.7,1.9,2.0,2.1,2.3,2.5,2.7],
    }

    for param, values in fine_params.items():
        for val in values:
            p = dict(best_params); p[param] = round(val, 3)
            r = run_backtest(p, PRICES_TRAIN)
            delta = r['ev'] - best_ev_train
            marker = '✅' if delta > 0 else '·'
            if delta > -0.1:  # only print near-best
                print(f"  {marker} fine {param}={val:<8}  EV={r['ev']:+.3f}  Δ{delta:+.3f}")
            total_experiments += 1
            if r['ev'] > best_ev_train:
                best_ev_train = r['ev']; best_params = dict(p)
                best_full = run_backtest(p, PRICES_FULL)

    # ══════════════════════════════════════════════════════════
    # PHASE 4 — Grid search: rr × min_prob × bb_std (focused)
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─'*88}")
    print(f"  PHASE 4 — Grid Search: rr × min_prob × bb_std")
    print(f"{'─'*88}")

    grid_rr      = [3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
    grid_prob    = [0.30, 0.33, 0.35, 0.38, 0.40]
    grid_bb_std  = [1.8, 2.0, 2.2, 2.5]

    grid_best_ev = best_ev_train
    grid_best    = None
    for rr in grid_rr:
        for prob in grid_prob:
            for bbs in grid_bb_std:
                p = dict(best_params)
                p['rr'] = rr; p['min_prob'] = prob; p['bb_std'] = bbs
                r = run_backtest(p, PRICES_TRAIN)
                total_experiments += 1
                if r['ev'] > grid_best_ev:
                    grid_best_ev = r['ev']; grid_best = dict(p)
                    print(f"  ✅ NEW GRID BEST: rr={rr} prob={prob} bbs={bbs}  EV={r['ev']:+.3f}")

    if grid_best and grid_best_ev > best_ev_train:
        best_ev_train = grid_best_ev; best_params = dict(grid_best)
        best_full = run_backtest(best_params, PRICES_FULL)
        print(f"  Grid promoted to overall best: EV={best_ev_train:+.3f}")
    else:
        print(f"  Grid search: no improvement over Phase 3 best (EV={best_ev_train:+.3f})")

    # ══════════════════════════════════════════════════════════
    # PHASE 5 — WALK-FORWARD VALIDATION
    # Validate best config + top-3 alternatives on UNSEEN data
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─'*88}")
    print(f"  PHASE 5 — WALK-FORWARD VALIDATION (Day {TRAIN_DAYS}–{TRAIN_DAYS+VAL_DAYS} — UNSEEN DATA)")
    print(f"{'─'*88}")
    print(f"  Strategy: Train on D0–D{TRAIN_DAYS}, validate on D{TRAIN_DAYS}–D{TRAIN_DAYS+VAL_DAYS}")
    print(f"  A config is ROBUST if val_EV ≥ 0.7 × train_EV (less than 30% decay)\n")

    # Candidates to validate
    val_candidates = [
        ('BEST (this run)',   best_params),
        ('BASELINE',         BASELINE),
        ('GEN3',             GEN3),
    ]
    # Add top-3 from phase 1
    for w in winners[:3]:
        val_candidates.append((f"P1-{w['param']}={w['value']}", w['params']))

    wf_results = []
    for label, params in val_candidates:
        r_train = run_backtest(params, PRICES_TRAIN)
        r_val   = run_backtest(params, PRICES_VAL)
        r_full  = run_backtest(params, PRICES_FULL)
        total_experiments += 3

        decay = (r_val['ev'] / r_train['ev']) if r_train['ev'] > 0 else 0
        robust = decay >= 0.70
        flag = '✅ ROBUST' if robust else '⚠️  DECAY ' if decay >= 0.40 else '❌ OVERFIT'

        print(f"  {flag}  {label[:38]:<40}")
        print(f"           Train EV={r_train['ev']:+.3f}  →  Val EV={r_val['ev']:+.3f}  (decay {decay:.0%})  Full={r_full['ev']:+.3f}")
        print(f"           Train: {r_train['wr']}%WR ${r_train['net']:+,.0f} | Val: {r_val['wr']}%WR ${r_val['net']:+,.0f} | Full: {r_full['wr']}%WR ${r_full['net']:+,.0f}")
        print()

        wf_results.append({
            'label': label, 'params': params,
            'train': {'ev': r_train['ev'], 'wr': r_train['wr'], 'net': r_train['net']},
            'val':   {'ev': r_val['ev'],   'wr': r_val['wr'],   'net': r_val['net']},
            'full':  {'ev': r_full['ev'],  'wr': r_full['wr'],  'net': r_full['net']},
            'decay': round(decay, 3), 'robust': robust,
        })

    elapsed = time.time() - t0

    # ══════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════════════════
    print(f"\n{'='*88}")
    print(f"  🏆 FINAL BEST — {total_experiments} EXPERIMENTS — WALK-FORWARD VALIDATED")
    print(f"{'='*88}")
    print(f"  Train EV:  {best_ev_train:+.4f}")
    print(f"  Full  EV:  {best_full['ev']:+.4f}  Grade: {best_full['grade']}")
    print(f"  Full  Net: ${best_full['net']:+,.2f}  WR: {best_full['wr']}%  DD: {best_full['max_dd']}%")
    print(f"  Trades:    {best_full['trades']} / 180 days ({best_full['trades']/180:.2f}/day)")
    print(f"  Params:    {json.dumps(best_params, separators=(',',':'))}")
    print(f"\n  Per-Regime (Full 180D):")
    rg = best_full.get('regimes', {})
    for name, emoji, days in [('bull','🐂','0–45'),('chop','〰️','45–90'),('bear','🐻','90–135'),('recovery','🔄','135–180')]:
        s = rg.get(name, {})
        verdict = '✅' if s.get('net', 0) > 0 else '❌'
        print(f"    {emoji} {name.upper():<10} (D{days}): {s.get('trades',0):>3} trades | {s.get('wr',0):>5.1f}%WR | ${s.get('net',0):>+8,.0f} | EV {s.get('ev',0):+.3f} {verdict}")
    print(f"\n  Walk-Forward robustness check:")
    wf_best = next((w for w in wf_results if w['label'].startswith('BEST')), None)
    if wf_best:
        flag = '✅ ROBUST' if wf_best['robust'] else '⚠️ DECAY'
        print(f"    {flag} — Train EV {wf_best['train']['ev']:+.3f} → Val EV {wf_best['val']['ev']:+.3f} (decay {wf_best['decay']:.0%})")
    print(f"\n  Total experiments: {total_experiments} | Time: {elapsed:.1f}s")

    output = {
        'version': 'expanded_v1',
        'experiments': total_experiments,
        'elapsed_s': round(elapsed, 1),
        'train_days': TRAIN_DAYS,
        'val_days': VAL_DAYS,
        'baseline': {'ev': baseline_full['ev'], 'grade': baseline_full['grade'], 'net': baseline_full['net']},
        'best': {
            'ev_train': round(best_ev_train, 4),
            'ev': best_full['ev'], 'grade': best_full['grade'],
            'net': best_full['net'], 'wr': best_full['wr'],
            'trades': best_full['trades'], 'max_dd': best_full['max_dd'],
            'params': best_params, 'regimes': best_full.get('regimes'),
        },
        'walk_forward': wf_results,
        'top_singles': [{'param': w['param'], 'value': w['value'], 'ev': w['ev'], 'delta': w['delta']} for w in winners[:15]],
    }

    with open('/tmp/autoresearch_expanded_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    print(f"  Saved: /tmp/autoresearch_expanded_results.json")
    return output

if __name__ == '__main__':
    run_sweep()
