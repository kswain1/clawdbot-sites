#!/usr/bin/env python3
"""
autorun_180.py — AutoResearch over 180-day / 4-regime dataset
Phases: Bull → Chop → Bear → Recovery
"""
import json, math, random, time, sys
sys.path.insert(0,'.')
from backtest_eval_180 import run_backtest, generate_prices_180

# Pre-generate prices once (shared across all experiments)
PRICES = generate_prices_180()

BASELINE = {'bb_period':20,'bb_std':2.0,'rr':2.8,'htf_bars':48,'min_prob':0.25,'entry_hours':[8,9,18,19,20]}
GEN3_30D = {'bb_period':20,'bb_std':2.0,'rr':4.0,'htf_bars':48,'min_prob':0.35,'entry_hours':[8,9,18,19,20]}

SEARCH_SPACE = {
    'bb_period':   [12, 15, 20, 25, 30],
    'bb_std':      [1.5, 1.8, 2.0, 2.2, 2.5, 3.0],
    'rr':          [2.0, 2.5, 2.8, 3.0, 3.5, 4.0, 4.5, 5.0],
    'htf_bars':    [12, 24, 48, 96],
    'min_prob':    [0.15, 0.20, 0.25, 0.30, 0.35, 0.40],
    'entry_hours': [
        [8,9,18,19,20],        # current
        [8,9,10],              # NY only
        [18,19,20],            # Asia only
        [7,8,9,10],            # Early NY
        [8,9,10,18,19,20],     # Full sessions
        [8,9],                 # NY power hour only
        list(range(6,12)),     # All morning
        list(range(17,22)),    # All evening
    ]
}

def fmt(r):
    return f"EV={r['ev']:+.3f} | WR={r['wr']:>5}% | Net=${r['net']:>+9,.0f} | DD={r['max_dd']:>5.1f}% | Grade={r['grade']}"

def regime_summary(r):
    rg = r.get('regimes',{})
    parts = []
    for name,emoji in [('bull','🐂'),('chop','〰️'),('bear','🐻'),('recovery','🔄')]:
        s = rg.get(name,{})
        parts.append(f"{emoji}{name[:4].upper()}:{s.get('wr',0):.0f}%WR/${s.get('net',0):+.0f}")
    return '  '.join(parts)

def run_sweep():
    t0 = time.time()
    print("\n" + "="*80)
    print("  AURA-V AUTORESEARCH — 180-DAY / 4-REGIME SWEEP")
    print("  Bull(45d) → Chop(45d) → Bear(45d) → Recovery(45d)")
    print("="*80)

    baseline = run_backtest(BASELINE, PRICES)
    gen3     = run_backtest(GEN3_30D, PRICES)

    print(f"\n  BASELINE (30D winner on 180D): {fmt(baseline)}")
    print(f"  {regime_summary(baseline)}")
    print(f"\n  GEN3 (rr=4.0+min_prob=0.35):  {fmt(gen3)}")
    print(f"  {regime_summary(gen3)}")
    print()

    all_results = []
    best_ev = baseline['ev']
    best_params = dict(BASELINE)
    best_result = baseline

    for param, values in SEARCH_SPACE.items():
        print(f"── {param} {'─'*(50-len(param))}")
        for val in values:
            params = dict(BASELINE); params[param] = val
            r = run_backtest(params, PRICES)
            delta = r['ev'] - baseline['ev']
            marker = '✅' if delta > 0.05 else '·'
            val_str = str(val)[:22]
            print(f"  {marker} {param}={val_str:<24} {fmt(r)}  Δ{delta:+.3f}")
            all_results.append({'param':param,'value':val,'result':r,'delta':delta,'params':dict(params)})
            if r['ev'] > best_ev: best_ev = r['ev']; best_params = dict(params); best_result = r

    # Top single-param winners
    winners = sorted([r for r in all_results if r['delta'] > 0.05], key=lambda x: x['delta'], reverse=True)

    print(f"\n{'='*80}")
    print(f"  TOP INDIVIDUAL WINS (Δ > +0.05 on 180D)")
    print(f"{'='*80}")
    for w in winners[:10]:
        print(f"  🏆 {w['param']}={str(w['value']):<24} EV={w['result']['ev']:+.3f}  Δ{w['delta']:+.3f}  Grade={w['result']['grade']}")
        print(f"     {regime_summary(w['result'])}")

    # Phase 2: combo sweep (top 5 winners)
    print(f"\n{'='*80}")
    print(f"  COMBINATION SWEEP")
    print(f"{'='*80}\n")

    combo_results = []
    top5 = winners[:5]

    # All-winners combo
    if top5:
        combo = dict(BASELINE)
        for w in top5: combo[w['param']] = w['value']
        r = run_backtest(combo, PRICES)
        delta = r['ev'] - baseline['ev']
        print(f"  ALL-5 COMBO: {fmt(r)}  Δ{delta:+.3f}")
        print(f"  {regime_summary(r)}")
        combo_results.append({'params':combo,'result':r,'note':'all-5'})
        if r['ev'] > best_ev: best_ev=r['ev']; best_params=dict(combo); best_result=r

    # Pairwise top-4
    for i in range(min(4,len(top5))):
        for j in range(i+1, min(4,len(top5))):
            p = dict(BASELINE)
            p[top5[i]['param']] = top5[i]['value']
            p[top5[j]['param']] = top5[j]['value']
            r = run_backtest(p, PRICES)
            delta = r['ev'] - baseline['ev']
            note = f"{top5[i]['param']}={top5[i]['value']} + {top5[j]['param']}={top5[j]['value']}"
            marker = '✅' if r['ev'] > best_ev else '·'
            print(f"  {marker} {note:<50} EV={r['ev']:+.3f}  Δ{delta:+.3f}  Grade={r['grade']}")
            combo_results.append({'params':p,'result':r,'note':note})
            if r['ev'] > best_ev: best_ev=r['ev']; best_params=dict(p); best_result=r

    # Phase 3: fine-tune best combo
    print(f"\n{'='*80}")
    print(f"  FINE-TUNE AROUND BEST COMBO")
    print(f"{'='*80}\n")

    fine_rr    = [3.0,3.2,3.5,3.8,4.0,4.2,4.5]
    fine_prob  = [0.28,0.30,0.32,0.35,0.38,0.40,0.42]
    fine_bb    = [13,14,15,16,17,18]

    for rr in fine_rr:
        p = dict(best_params); p['rr'] = rr
        r = run_backtest(p, PRICES)
        delta = r['ev'] - best_ev
        marker = '✅' if delta > 0 else '·'
        print(f"  {marker} rr={rr}  {fmt(r)}  Δ{delta:+.3f}")
        if r['ev'] > best_ev: best_ev=r['ev']; best_params=dict(p); best_result=r

    print()
    for prob in fine_prob:
        p = dict(best_params); p['min_prob'] = prob
        r = run_backtest(p, PRICES)
        delta = r['ev'] - best_ev
        marker = '✅' if delta > 0 else '·'
        print(f"  {marker} min_prob={prob}  {fmt(r)}  Δ{delta:+.3f}")
        if r['ev'] > best_ev: best_ev=r['ev']; best_params=dict(p); best_result=r

    print()
    for bp in fine_bb:
        p = dict(best_params); p['bb_period'] = bp
        r = run_backtest(p, PRICES)
        delta = r['ev'] - best_ev
        marker = '✅' if delta > 0 else '·'
        print(f"  {marker} bb_period={bp}  {fmt(r)}  Δ{delta:+.3f}")
        if r['ev'] > best_ev: best_ev=r['ev']; best_params=dict(p); best_result=r

    elapsed = time.time()-t0

    print(f"\n{'='*80}")
    print(f"  🏆 FINAL BEST — 180-DAY VALIDATED")
    print(f"{'='*80}")
    print(f"  EV:     {best_result['ev']:+.4f}  (baseline was {baseline['ev']:+.4f})")
    print(f"  Grade:  {best_result['grade']}")
    print(f"  Net:    ${best_result['net']:+,.2f}")
    print(f"  WR:     {best_result['wr']}%")
    print(f"  Trades: {best_result['trades']}")
    print(f"  Max DD: {best_result['max_dd']}%")
    print(f"  Params: {json.dumps(best_params, separators=(',',':'))}")
    print(f"\n  Per-Regime Breakdown:")
    rg = best_result.get('regimes',{})
    for name,emoji,days in [('bull','🐂','0–45'),('chop','〰️','45–90'),('bear','🐻','90–135'),('recovery','🔄','135–180')]:
        s = rg.get(name,{})
        verdict = '✅' if s.get('net',0) > 0 else '❌'
        print(f"    {emoji} {name.upper():<10} (Day {days}): {s.get('trades',0)} trades | {s.get('wr',0)}% WR | Net ${s.get('net',0):+,.0f} | EV {s.get('ev',0):+.3f}  {verdict}")
    print(f"\n  Total experiments: {len(all_results)+len(combo_results)} | Time: {elapsed:.1f}s")

    output = {
        'days': 180,
        'regimes': ['bull(0-44)','chop(45-89)','bear(90-134)','recovery(135-179)'],
        'baseline': {'ev':baseline['ev'],'grade':baseline['grade'],'net':baseline['net'],'regimes':baseline.get('regimes')},
        'gen3_30d': {'ev':gen3['ev'],'grade':gen3['grade'],'net':gen3['net'],'regimes':gen3.get('regimes')},
        'best': {'ev':best_result['ev'],'grade':best_result['grade'],'net':best_result['net'],'wr':best_result['wr'],'trades':best_result['trades'],'max_dd':best_result['max_dd'],'params':best_params,'regimes':best_result.get('regimes')},
        'winners': [{'param':w['param'],'value':w['value'],'ev':w['result']['ev'],'delta':w['delta']} for w in winners[:10]],
        'experiments': len(all_results)+len(combo_results),
        'elapsed_s': round(elapsed,1),
    }
    with open('/tmp/autoresearch_180d_results.json','w') as f:
        json.dump(output, f, indent=2)
    print(f"\n  Saved: /tmp/autoresearch_180d_results.json")
    return output

if __name__ == '__main__':
    run_sweep()
