#!/usr/bin/env python3
"""
autorun_session.py — Session-Specialized AutoResearch
───────────────────────────────────────────────────────
Runs 3 separate optimization sweeps, each filtered to a specific trading session:

  MODEL 1 — ASIA SESSION    entry_hours restricted to [17,18,19,20]  (5–8 PM CST)
  MODEL 2 — NEW YORK SESSION entry_hours restricted to [8,9,10]       (8–10:30 AM CST)
  MODEL 3 — OPEN / ANY TIME  entry_hours = any hour (24/7 baseline)

Each model runs the same 5-phase sweep (single-param → combo → fine-tune → grid → WF).
Results saved per-session + combined into autoresearch_session_results.json.
Best per-session promoted independently.

Usage:
  python autorun_session.py
  python autorun_session.py --session asia
  python autorun_session.py --session ny
  python autorun_session.py --session open
"""
import json, math, time, sys, itertools
sys.path.insert(0, '.')
from backtest_eval_180 import run_backtest, generate_prices_180

# ── Price series ──
PRICES_FULL  = generate_prices_180()
BARS_PER_DAY = 288
TRAIN_DAYS   = 120
VAL_DAYS     = 60
PRICES_TRAIN = PRICES_FULL[:TRAIN_DAYS * BARS_PER_DAY]
PRICES_VAL   = PRICES_FULL[TRAIN_DAYS * BARS_PER_DAY:]

# ── Session Definitions ──
SESSIONS = {
    'asia': {
        'name':        'Asia Session',
        'emoji':       '🌏',
        'hours':       [17, 18, 19, 20],        # 5–8 PM CST
        'description': '5:00–8:00 PM CST  (Tokyo/Sydney open)',
    },
    'ny': {
        'name':        'New York Session',
        'emoji':       '🗽',
        'hours':       [8, 9, 10],              # 8–10:30 AM CST
        'description': '8:00–10:30 AM CST  (NY open power hour)',
    },
    'open': {
        'name':        'Open / Any Time',
        'emoji':       '🌐',
        'hours':       list(range(24)),          # 24/7
        'description': 'All hours  (maximum opportunity)',
    },
}

# ── Search space (param ranges — same for all sessions, hours locked per session) ──
BB_PERIODS  = [10, 12, 14, 15, 17, 18, 20, 22, 25, 28, 30]
BB_STDS     = [1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0]
RRS         = [2.0, 2.8, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.3]
HTF_BARS    = [6, 12, 24, 48, 72, 96]
MIN_PROBS   = [0.15, 0.20, 0.25, 0.30, 0.35, 0.38, 0.40, 0.42, 0.44, 0.48, 0.50]

BASELINE_EV = 4.840   # current production EV — floor for any promotion


def base_params(session_key):
    return {
        'bb_period':   20,
        'bb_std':      2.0,
        'rr':          2.8,
        'htf_bars':    48,
        'min_prob':    0.25,
        'entry_hours': SESSIONS[session_key]['hours'],
    }


def sweep_session(session_key, verbose=True):
    sess   = SESSIONS[session_key]
    hours  = sess['hours']
    t0     = time.time()
    total  = 0
    winners = []

    def run(params):
        return run_backtest(params, PRICES_FULL)

    def p(params_override):
        nonlocal total
        p = dict(base_params(session_key))
        p.update(params_override)
        p['entry_hours'] = hours   # lock hours to session
        total += 1
        return p

    if verbose:
        print(f"\n{'='*70}")
        print(f"  {sess['emoji']}  SESSION MODEL: {sess['name'].upper()}")
        print(f"  Hours: {hours}  ({sess['description']})")
        print(f"{'='*70}")

    # ── Phase 1: Single-param sweep ──
    if verbose: print(f"\n── Phase 1: Single-param sweep ──")
    phase1_results = []
    for bb_period in BB_PERIODS:
        r = run(p({'bb_period': bb_period})); phase1_results.append(('bb_period', bb_period, r))
    for bb_std in BB_STDS:
        r = run(p({'bb_std': bb_std}));       phase1_results.append(('bb_std', bb_std, r))
    for rr in RRS:
        r = run(p({'rr': rr}));               phase1_results.append(('rr', rr, r))
    for htf in HTF_BARS:
        r = run(p({'htf_bars': htf}));        phase1_results.append(('htf_bars', htf, r))
    for mp in MIN_PROBS:
        r = run(p({'min_prob': mp}));         phase1_results.append(('min_prob', mp, r))

    # Find top single-param wins
    phase1_results.sort(key=lambda x: x[2]['ev'], reverse=True)
    for param, val, r in phase1_results[:5]:
        if verbose:
            print(f"  {'+' if r['ev']>0 else ' '} {param}={val:<6} EV={r['ev']:+.3f}  {r['grade']}  WR={r['wr']}%  ${r['net']:+,.0f}")
        winners.append({'param': param, 'value': val, 'ev': r['ev'], 'params': p({param: val})})

    best_ev    = phase1_results[0][2]['ev']
    best_params = dict(base_params(session_key))
    best_params[phase1_results[0][0]] = phase1_results[0][1]
    best_params['entry_hours'] = hours

    # ── Phase 2: Combo sweep (top 3 winners) ──
    if verbose: print(f"\n── Phase 2: Combo sweep ──")
    top3 = [(w['param'], w['value']) for w in winners[:3]]
    for i, (p1, v1) in enumerate(top3):
        for j, (p2, v2) in enumerate(top3):
            if i >= j: continue
            params = p({p1: v1, p2: v2})
            r = run(params)
            if r['ev'] > best_ev:
                best_ev = r['ev']; best_params = params
                if verbose: print(f"  ✅ NEW BEST  {p1}={v1} + {p2}={v2}  EV={r['ev']:+.3f}  ${r['net']:+,.0f}")

    # ── Phase 3: Fine-tune best combo ──
    if verbose: print(f"\n── Phase 3: Fine-tune ──")
    for rr in [best_params['rr'] - 0.5, best_params['rr'] + 0.5, best_params['rr'] + 1.0]:
        if rr <= 0: continue
        params = dict(best_params); params['rr'] = round(rr, 1); params['entry_hours'] = hours
        r = run(params)
        if r['ev'] > best_ev:
            best_ev = r['ev']; best_params = params
            if verbose: print(f"  ✅ Fine-tune rr={rr}  EV={r['ev']:+.3f}")

    for mp in [best_params['min_prob'] - 0.05, best_params['min_prob'] + 0.05]:
        if mp < 0 or mp > 1: continue
        mp = round(mp, 2)
        params = dict(best_params); params['min_prob'] = mp; params['entry_hours'] = hours
        r = run(params)
        if r['ev'] > best_ev:
            best_ev = r['ev']; best_params = params
            if verbose: print(f"  ✅ Fine-tune min_prob={mp}  EV={r['ev']:+.3f}")

    # ── Phase 4: Mini grid search ──
    if verbose: print(f"\n── Phase 4: Grid search ──")
    top_rrs  = sorted(set([best_params['rr']] + [v for k,v in top3 if k=='rr'] + [4.5,5.0,6.3]), key=lambda x: abs(x-best_params['rr']))[:4]
    top_mps  = sorted(set([best_params['min_prob']] + [v for k,v in top3 if k=='min_prob'] + [0.35,0.42,0.44]), key=lambda x: abs(x-best_params['min_prob']))[:4]
    top_stds = sorted(set([best_params['bb_std']] + [2.0,2.5,2.8]), key=lambda x: abs(x-best_params['bb_std']))[:3]

    for rr, mp, bs in itertools.product(top_rrs, top_mps, top_stds):
        params = dict(best_params); params.update({'rr':rr,'min_prob':mp,'bb_std':bs,'entry_hours':hours})
        r = run(params)
        if r['ev'] > best_ev:
            best_ev = r['ev']; best_params = params
            if verbose: print(f"  ✅ Grid rr={rr} mp={mp} std={bs}  EV={r['ev']:+.3f}  ${r['net']:+,.0f}")

    # ── Phase 5: Walk-Forward Validation ──
    if verbose: print(f"\n── Phase 5: Walk-Forward Validation ──")
    r_train = run_backtest(best_params, PRICES_TRAIN)
    r_val   = run_backtest(best_params, PRICES_VAL)
    r_full  = run_backtest(best_params, PRICES_FULL)
    decay   = (r_val['ev'] / r_train['ev']) if r_train['ev'] > 0 else 0
    robust  = decay >= 0.70
    flag    = '✅ ROBUST' if robust else ('⚠️  DECAY' if decay >= 0.40 else '❌ OVERFIT')

    if verbose:
        print(f"  {flag}  Train EV={r_train['ev']:+.3f}  →  Val EV={r_val['ev']:+.3f}  (decay {decay:.0%})")
        print(f"  Full 180D: EV={r_full['ev']:+.3f}  Grade={r_full['grade']}  WR={r_full['wr']}%  DD={r_full['max_dd']}%  Net=${r_full['net']:+,.0f}")
        print(f"  Params: {json.dumps({k:v for k,v in best_params.items() if k!='entry_hours'}, separators=(',',':'))}")
        print(f"  Entry hours: {hours}  ({sess['description']})")

    elapsed = round(time.time() - t0, 1)
    if verbose:
        print(f"  Experiments: {total}  |  Time: {elapsed}s")

    return {
        'session':      session_key,
        'name':         sess['name'],
        'emoji':        sess['emoji'],
        'description':  sess['description'],
        'hours':        hours,
        'experiments':  total,
        'elapsed_s':    elapsed,
        'best': {
            'ev':       r_full['ev'],
            'ev_train': r_train['ev'],
            'ev_val':   r_val['ev'],
            'wf_decay': round(decay, 3),
            'robust':   robust,
            'grade':    r_full['grade'],
            'net':      r_full['net'],
            'wr':       r_full['wr'],
            'max_dd':   r_full['max_dd'],
            'trades':   r_full['trades'],
            'params':   best_params,
            'regimes':  r_full.get('regimes', {}),
        },
        'top_singles': [{'param': w['param'], 'value': w['value'], 'ev': w['ev']} for w in winners[:10]],
    }


def run_all(session_filter=None):
    print(f"\n{'#'*70}")
    print(f"  AURA SESSION-SPECIALIZED AUTORESEARCH")
    print(f"  Asia Model | New York Model | Open Model")
    print(f"{'#'*70}")
    t0 = time.time()

    sessions_to_run = [session_filter] if session_filter else ['asia', 'ny', 'open']
    results = {}

    for sk in sessions_to_run:
        results[sk] = sweep_session(sk, verbose=True)

    # ── Combined summary ──
    print(f"\n{'='*70}")
    print(f"  🏆  SESSION MODEL COMPARISON")
    print(f"{'='*70}")
    print(f"  {'Session':<22} {'EV':>8}  {'Grade':>6}  {'WR':>6}  {'DD':>6}  {'Net':>12}  {'WF'}")
    print(f"  {'─'*70}")
    for sk, r in results.items():
        b = r['best']
        flag = '✅' if b['robust'] else '⚠️ '
        print(f"  {r['emoji']} {r['name']:<20} {b['ev']:>+8.4f}  {b['grade']:>6}  {b['wr']:>5.1f}%  {b['max_dd']:>5.1f}%  ${b['net']:>+10,.0f}  {flag}")

    # Overall best
    overall_best_key = max(results, key=lambda k: results[k]['best']['ev'])
    overall_best     = results[overall_best_key]
    print(f"\n  🥇 Overall winner: {overall_best['emoji']} {overall_best['name']}  EV {overall_best['best']['ev']:+.4f}")

    total_elapsed = round(time.time() - t0, 1)
    print(f"  Total experiments: {sum(r['experiments'] for r in results.values())}  |  Time: {total_elapsed}s")

    output = {
        'version':        'session_v1',
        'sessions':       results,
        'overall_best':   overall_best_key,
        'total_experiments': sum(r['experiments'] for r in results.values()),
        'elapsed_s':      total_elapsed,
    }

    out_path = '/tmp/autoresearch_session_results.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"  Saved: {out_path}")

    # Also update autoresearch_latest.json with overall best
    best_result = overall_best['best']
    latest = {
        'version':      'session_v1',
        'experiments':  output['total_experiments'],
        'elapsed_s':    total_elapsed,
        'train_days':   TRAIN_DAYS,
        'val_days':     VAL_DAYS,
        'best': {
            'ev':       best_result['ev'],
            'ev_train': best_result['ev_train'],
            'grade':    best_result['grade'],
            'net':      best_result['net'],
            'wr':       best_result['wr'],
            'trades':   best_result['trades'],
            'max_dd':   best_result['max_dd'],
            'params':   best_result['params'],
            'regimes':  best_result['regimes'],
            'session':  overall_best_key,
        },
        'session_summary': {
            sk: {
                'ev': r['best']['ev'], 'grade': r['best']['grade'],
                'net': r['best']['net'], 'wr': r['best']['wr'],
                'robust': r['best']['robust'], 'params': r['best']['params'],
            }
            for sk, r in results.items()
        },
        'walk_forward': [
            {
                'label': f"{r['emoji']} {r['name']}",
                'params': r['best']['params'],
                'train': {'ev': r['best']['ev_train']},
                'val':   {'ev': r['best']['ev_val']},
                'full':  {'ev': r['best']['ev']},
                'decay': r['best']['wf_decay'],
                'robust': r['best']['robust'],
            }
            for r in results.values()
        ],
    }
    with open('/tmp/autoresearch_expanded_results.json', 'w') as f:
        json.dump(latest, f, indent=2)
    print(f"  Updated: /tmp/autoresearch_expanded_results.json  (used by auto_promote.py)")

    return output


if __name__ == '__main__':
    session_filter = None
    if '--session' in sys.argv:
        idx = sys.argv.index('--session')
        if idx + 1 < len(sys.argv):
            session_filter = sys.argv[idx + 1].lower()
            if session_filter not in SESSIONS:
                print(f"Unknown session '{session_filter}'. Choose: asia, ny, open")
                sys.exit(1)
    run_all(session_filter)
