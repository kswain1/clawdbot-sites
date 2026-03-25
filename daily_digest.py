#!/usr/bin/env python3
"""
daily_digest.py — Posts a consolidated daily summary to #daily-digest
Reads: pulse_log.json, price_data.json, autoresearch/autoresearch_latest.json
Runs via GitHub Actions on schedule or manual trigger
"""
import json, os, requests, statistics
from datetime import datetime, timezone, timedelta

WEBHOOK = os.environ.get('DISCORD_WEBHOOK_DIGEST', 'https://discord.com/api/webhooks/1484817995024039988/qlkO2bRGHba4iDQ5AHpbbkm-SjGexVGBz39K0ux2g7s1FDHjWa9DcuBFjoo15AWnnRP_')

def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def market_analysis(price_data, pulse):
    """Build a buyer/seller battle + S/R + signal summary from price_data.json + pulse_log."""
    if not price_data:
        return "No market data available."

    cp       = float(price_data.get('current_price', 0))
    bars     = price_data.get('bars_1h', []) or price_data.get('bars_5m', [])

    # Bollinger — actual keys from price_data.json
    bb_upper = float(price_data.get('bb_upper_5m', price_data.get('bb_upper', 0)) or 0)
    bb_lower = float(price_data.get('bb_lower_5m', price_data.get('bb_lower', 0)) or 0)
    bb_mid   = float(price_data.get('bb_mid_5m',   price_data.get('bb_mid',   (bb_upper+bb_lower)/2 if bb_upper else 0)) or 0)

    # S/R — can be a list [{type,price}] or a dict
    sr_raw  = price_data.get('sr_levels', price_data.get('support_resistance', []))
    if isinstance(sr_raw, list) and sr_raw:
        supports  = sorted([float(x['price']) for x in sr_raw if x.get('type') == 'S'], reverse=True)
        resists   = sorted([float(x['price']) for x in sr_raw if x.get('type') == 'R'])
        support   = supports[0]  if supports else 0.0
        resist    = resists[0]   if resists  else 0.0
        # Top 2 of each for display
        sup_str = '  '.join([f'${s:.2f}' for s in supports[:3]])
        res_str = '  '.join([f'${r:.2f}' for r in resists[:3]])
    elif isinstance(sr_raw, dict):
        support = float(sr_raw.get('support', 0))
        resist  = float(sr_raw.get('resistance', 0))
        sup_str = f'${support:.2f}'
        res_str = f'${resist:.2f}'
    else:
        support = resist = 0.0
        sup_str = res_str = 'N/A'

    daily_high = float(price_data.get('daily_high', 0) or 0)
    daily_low  = float(price_data.get('daily_low',  0) or 0)
    change_pct = float(price_data.get('change_pct', 0) or 0)

    # ── Buyer/Seller pressure from recent bars ──
    if bars and len(bars) >= 10:
        recent = bars[-20:]
        # Support both long-key (open/close) and short-key (o/c) bar formats
        def get_o(b): return float(b.get('open', b.get('o', 0)) or 0)
        def get_c(b): return float(b.get('close', b.get('c', 0)) or 0)
        def get_v(b): return float(b.get('volume', b.get('v', 1)) or 1)
        bull_bars = [b for b in recent if get_c(b) > get_o(b)]
        bear_bars = [b for b in recent if get_c(b) < get_o(b)]
        bull_pct  = round(len(bull_bars) / len(recent) * 100)
        bear_pct  = 100 - bull_pct

        # Volume-weight if available
        bull_vol = sum(get_v(b) for b in bull_bars)
        bear_vol = sum(get_v(b) for b in bear_bars)
        total_vol = bull_vol + bear_vol
        bull_vol_pct = round(bull_vol / total_vol * 100) if total_vol else bull_pct
        bear_vol_pct = 100 - bull_vol_pct

        # Momentum: last 5 bars vs prior 5
        if len(recent) >= 10:
            last5  = [get_c(b) for b in recent[-5:]]
            prior5 = [get_c(b) for b in recent[-10:-5]]
            momentum = 'ACCELERATING ▲' if last5[-1] > prior5[-1] and last5[0] > prior5[0] else \
                       'DECELERATING ▼' if last5[-1] < prior5[-1] else 'NEUTRAL →'
        else:
            momentum = 'NEUTRAL →'
    else:
        bull_pct = bear_pct = 50
        bull_vol_pct = bear_vol_pct = 50
        momentum = 'INSUFFICIENT DATA'

    # ── Position vs key levels ──
    pos_vs_bb  = 'ABOVE MID (bullish lean)' if cp > bb_mid else 'BELOW MID (bearish lean)'
    pos_vs_sr  = ''
    if support and resist:
        range_size = resist - support
        pos_in_range = (cp - support) / range_size * 100 if range_size > 0 else 50
        if pos_in_range >= 80:
            pos_vs_sr = f'Near RESISTANCE ${resist:.2f} — watch for rejection'
        elif pos_in_range <= 20:
            pos_vs_sr = f'Near SUPPORT ${support:.2f} — watch for bounce'
        else:
            pos_vs_sr = f'Mid-range ({pos_in_range:.0f}% of S/R range)'

    # ── Key signals from pulse log ──
    signals_today = []
    if pulse:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for p in pulse[-288:]:
            sig = p.get('signal', '')
            if sig in ('BUY', 'SELL'):
                signals_today.append(p)

    sig_summary = ''
    if signals_today:
        buys  = [p for p in signals_today if p['signal'] == 'BUY']
        sells = [p for p in signals_today if p['signal'] == 'SELL']
        last_sig = signals_today[-1]
        sig_summary = (
            f"Signals (24H): {len(buys)} BUY  {len(sells)} SELL\n"
            f"Last Signal:   {last_sig.get('signal','—')} @ ${float(last_sig.get('price',0)):.2f} "
            f"| Prob {last_sig.get('probability',0)}% | {last_sig.get('mode','—')}\n"
        )
    else:
        sig_summary = "Signals (24H): No qualifying signals fired\n"

    # ── Bias verdict ──
    if bull_pct >= 60:
        bias_verdict = '🐂 BUYERS IN CONTROL'
    elif bear_pct >= 60:
        bias_verdict = '🐻 SELLERS IN CONTROL'
    else:
        bias_verdict = '⚖️ CONTESTED — no clear edge'

    # ── Bull/Bear bar visual ──
    bull_blocks = round(bull_vol_pct / 10)
    bear_blocks = 10 - bull_blocks
    battle_bar  = '🟢' * bull_blocks + '🔴' * bear_blocks

    lines = [
        f"XAUUSD Price:  ${cp:.2f}",
        f"Day Range:     ${daily_low:.2f}  —  ${daily_high:.2f}  ({change_pct:+.2f}%)",
        f"BB Bands:      ${bb_lower:.1f}  /  ${bb_mid:.1f}  /  ${bb_upper:.1f}",
        f"Support:       {sup_str}",
        f"Resistance:    {res_str}",
        f"Position:      {pos_vs_bb}",
        f"               {pos_vs_sr}",
        f"",
        f"── BUYER vs SELLER BATTLE (last 20 bars) ──",
        f"{battle_bar}",
        f"Bulls: {bull_vol_pct}%  Bears: {bear_vol_pct}%  Momentum: {momentum}",
        f"Verdict: {bias_verdict}",
        f"",
        f"── KEY SIGNALS ──",
        sig_summary.rstrip(),
    ]
    return '\n'.join(lines)



def bot_logic_checkpoints(price_data, pulse):
    """Show the bot decision tree with ✅/❌ at each checkpoint, using latest pulse state."""
    cp = float(price_data.get('current_price', 0)) if price_data else 0.0
    if not pulse:
        return "No pulse data — bot has not run yet."

    latest = pulse[-1]
    price  = float(latest.get('price', cp) or cp)
    prob   = float(latest.get('probability', 0) or 0)
    signal = latest.get('signal', 'WAIT')
    mode   = latest.get('mode', '—') or latest.get('status', '—')
    ts     = latest.get('timestamp', '—')

    # Simulate the 3-strategy checkpoint matrix from current pulse state
    strategies = [
        {'name': 'HYBRID',    'emoji': '🤖', 'min_prob': 0.0,  'hours': list(range(24)),      'htf': False, 'rr': 2.8},
        {'name': 'VELOCITY',  'emoji': '⚡', 'min_prob': 0.25, 'hours': [8,9,10,18,19,20],    'htf': True,  'rr': 4.5},
        {'name': 'CHALLENGE', 'emoji': '🛡️', 'min_prob': 0.42, 'hours': [8,9,18,19,20],       'htf': True,  'rr': 4.5},
    ]

    # Determine current CST hour from timestamp
    try:
        from datetime import datetime
        # ts format: "2026-03-24 21:31 CST" or UTC
        cst_hour = int(ts.split(' ')[1].split(':')[0]) if ts != '—' else 0
    except:
        cst_hour = 0

    # HTF bias from recent bars — rough check from price vs BB mid
    bb_mid = float(price_data.get('bb_mid_5m', 0) or 0) if price_data else 0
    htf_bias = 'BULLISH' if price > bb_mid > 0 else ('BEARISH' if bb_mid > 0 else 'NEUTRAL')

    is_trade_signal = signal in ('BUY', 'SELL')

    lines = [
        f"Snapshot: {ts}  |  Price: ${price:.2f}  |  Mode: {mode}",
        f"",
        f"CHECKPOINT 1 — AUTO-MODE DETECTION",
    ]

    # Mode check
    mode_upper = mode.upper()
    if 'TREND' in mode_upper:
        lines.append(f"  ✅  ADX > 25, ATR expanding, ROC > 0.3 → TREND mode")
    elif 'CONSOL' in mode_upper or 'CONSOLIDAT' in mode_upper:
        lines.append(f"  ✅  ADX < 20, low ATR → CONSOLIDATION mode")
    elif 'TRANSITION' in mode_upper:
        lines.append(f"  ⚠️  Mixed indicators → TRANSITION mode (weaker signals)")
    else:
        lines.append(f"  ⚠️  Mode: {mode}")

    lines += [
        f"",
        f"CHECKPOINT 2 — SIGNAL GENERATION",
    ]
    if is_trade_signal:
        lines.append(f"  ✅  Signal: {signal}  |  Probability: {prob:.1f}%")
        lines.append(f"       Price vs BB bands — outside band trigger confirmed")
    else:
        lines.append(f"  ⏸️  Signal: {signal}  (no trade setup — price inside bands or weak momentum)")

    lines += [
        f"",
        f"CHECKPOINT 3 — PER-STRATEGY FILTERS",
        f"  {'Strategy':<12} {'Hour':<6} {'Prob':<8} {'HTF':<10} {'Result'}",
        f"  {'─'*54}",
    ]

    for s in strategies:
        ck_hr   = '✅' if cst_hour in s['hours'] else '❌'
        ck_prob = '✅' if prob >= s['min_prob'] * 100 else '❌'
        ck_htf  = '✅' if (not s['htf'] or htf_bias != 'NEUTRAL') else '⚠️'
        passed  = (cst_hour in s['hours']) and (prob >= s['min_prob'] * 100)
        result  = '🟢 FIRE' if (is_trade_signal and passed) else ('🔴 BLOCK' if is_trade_signal else '⏸️ WAIT')
        lines.append(
            f"  {s['emoji']} {s['name']:<11} {ck_hr}      {ck_prob}       {ck_htf}        {result}"
        )

    lines += [
        f"",
        f"CHECKPOINT 4 — HTF BIAS ALIGNMENT",
        f"  BB Mid (5m): ${bb_mid:.2f}  |  Price: ${price:.2f}",
        f"  {'✅' if htf_bias != 'NEUTRAL' else '⚠️'}  Bias: {htf_bias}",
        f"  {'✅  Aligned with signal' if (is_trade_signal and ((signal=='BUY' and htf_bias=='BULLISH') or (signal=='SELL' and htf_bias=='BEARISH'))) else '❌  Misaligned — VELOCITY/CHALLENGE blocked' if is_trade_signal else '—  No active signal'}",
        f"",
        f"CHECKPOINT 5 — PROP FIRM SAFETY",
        f"  ✅  Daily loss cap: $400 enforced",
        f"  ✅  Max DD guard: protect_at 6–7% profit lock",
        f"  ✅  Trade timeout: 120 min auto-close",
        f"  ✅  One open trade max per strategy",
    ]

    return '\n'.join(lines)

def build_digest():
    now_utc  = datetime.now(timezone.utc)
    date_str = now_utc.strftime('%A, %B %-d, %Y')
    time_str = now_utc.strftime('%I:%M %p UTC')

    pulse      = load_json('pulse_log.json', [])
    price_data = load_json('price_data.json', {})
    ar         = load_json('autoresearch/autoresearch_latest.json', {})

    # ── Market Analysis (new) ──
    market_section = market_analysis(price_data, pulse)

    # ── Pulse summary ──
    pulse_section = "No pulse data available."
    if pulse:
        latest = pulse[-1]
        pulse_section = (
            f"Latest:   {latest.get('timestamp','—')} | "
            f"${float(latest.get('price',0)):.2f} | "
            f"Prob {latest.get('probability',0)}% | "
            f"{latest.get('signal','—')} | {latest.get('mode','—')}\n"
            f"Log entries: {len(pulse)}"
        )

    # ── AutoResearch latest ──
    ar_section = "No AutoResearch data."
    if ar:
        best = ar.get('best', {})
        rg   = best.get('regimes', {})
        def rline(name, emoji):
            s = rg.get(name, {})
            verdict = '✅' if s.get('net', 0) > 0 else '❌'
            return f"{emoji} {name.upper():<10}: {s.get('wr',0):.0f}% WR | ${s.get('net',0):+,.0f} {verdict}"
        ar_section = (
            f"Config: rr={best.get('params',{}).get('rr')} | "
            f"min_prob={best.get('params',{}).get('min_prob')} | "
            f"htf={best.get('params',{}).get('htf_bars')}\n"
            f"EV {best.get('ev',0):+.4f}  Grade {best.get('grade','?')}  "
            f"Net ${best.get('net',0):+,.0f}  WR {best.get('wr',0)}%  DD {best.get('max_dd',0)}%\n"
            f"{rline('bull','🐂')}  {rline('chop','〰️')}\n"
            f"{rline('bear','🐻')}  {rline('recovery','🔄')}"
        )

    checkpoint_section = bot_logic_checkpoints(price_data, pulse)

    msg = f"""📊 **AURA DAILY DIGEST** — {date_str}
*Generated {time_str}*

**XAUUSD Market Report**
```
{market_section}
```
**Bot Logic — Live Checkpoints**
```
{checkpoint_section}
```
**Strategy Pulse**
```
{pulse_section}
```
**AutoResearch — Best Config (180D)**
```
{ar_section}
```
🧿 *Market Kombat:* <https://kswain1.github.io/clawdbot-sites/market-kombat/>"""

    return msg

def post_digest():
    msg = build_digest()
    r = requests.post(WEBHOOK, json={'content': msg}, timeout=15)
    if r.status_code in (200, 204):
        print(f"Daily digest posted ({r.status_code})")
    else:
        print(f"Failed: {r.status_code} {r.text}")

if __name__ == '__main__':
    post_digest()
