#!/usr/bin/env python3
"""
daily_digest.py — Posts a consolidated daily summary to #daily-digest
Reads: pulse_log.json, price_data.json, autoresearch/autoresearch_latest.json
Runs via GitHub Actions on schedule or manual trigger
"""
import json, os, requests
from datetime import datetime, timezone

WEBHOOK = "https://discord.com/api/webhooks/1484817995024039988/qlkO2bRGHba4iDQ5AHpbbkm-SjGexVGBz39K0ux2g7s1FDHjWa9DcuBFjoo15AWnnRP_"

def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def build_digest():
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime('%A, %B %-d, %Y')
    time_str = now_utc.strftime('%I:%M %p UTC')

    # ── Pulse log summary ──
    pulse = load_json('pulse_log.json', [])
    pulse_section = "No pulse data available."
    if pulse:
        today_pulses = pulse[-288:]  # last 24h (5-min bars)
        signals = [p for p in today_pulses if p.get('signal') in ('BUY','SELL')]
        buys  = [p for p in signals if p.get('signal') == 'BUY']
        sells = [p for p in signals if p.get('signal') == 'SELL']
        latest = pulse[-1]
        pulse_section = (
            f"Latest:   {latest.get('timestamp','—')} | "
            f"${float(latest.get('price',0)):.2f} | "
            f"Prob {latest.get('probability',0)}% | "
            f"{latest.get('signal','—')} | {latest.get('mode','—')}\n"
            f"24H Signals: {len(buys)} BUY  {len(sells)} SELL  ({len(signals)} total)\n"
            f"Total log entries: {len(pulse)}"
        )

    # ── Price data ──
    price_data = load_json('price_data.json', {})
    price_section = "No price data available."
    if price_data:
        cp = price_data.get('current_price')
        sr = price_data.get('support_resistance', {})
        bb = price_data.get('bollinger', {})
        price_section = (
            f"XAUUSD:  ${float(cp):.2f}\n"
            f"BB:      {float(bb.get('lower',0)):.1f} / {float(bb.get('upper',0)):.1f}\n"
            f"Support: ${float(sr.get('support',0)):.2f}   Resistance: ${float(sr.get('resistance',0)):.2f}"
        ) if cp else "Price unavailable"

    # ── AutoResearch latest ──
    ar = load_json('autoresearch/autoresearch_latest.json', {})
    ar_section = "No AutoResearch data."
    if ar:
        best = ar.get('best', {})
        rg = best.get('regimes', {})
        def rline(name, emoji):
            s = rg.get(name, {})
            verdict = '✅' if s.get('net', 0) > 0 else '❌'
            return f"{emoji} {name.upper():<10}: {s.get('wr',0):.0f}% WR | ${s.get('net',0):+,.0f} {verdict}"
        ar_section = (
            f"Best Config: rr={best.get('params',{}).get('rr')} | "
            f"min_prob={best.get('params',{}).get('min_prob')} | "
            f"htf={best.get('params',{}).get('htf_bars')}\n"
            f"EV {best.get('ev',0):+.4f}  Grade {best.get('grade','?')}  "
            f"Net ${best.get('net',0):+,.0f}  WR {best.get('wr',0)}%  "
            f"DD {best.get('max_dd',0)}%\n"
            f"{rline('bull','🐂')}  {rline('chop','〰️')}\n"
            f"{rline('bear','🐻')}  {rline('recovery','🔄')}"
        )

    msg = f"""📊 **AURA DAILY DIGEST** — {date_str}
*Generated {time_str}*

**Market Intelligence**
```
{price_section}
```
**Strategy Pulse (24H)**
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
