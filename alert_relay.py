#!/usr/bin/env python3
"""
Aura-V 2.0 HYBRID Pulse Relay
- TREND mode     → IMMEDIATE entry (catch momentum)
- CONSOLIDATION  → 20-MIN countdown (filter fakeouts)
- TRANSITION     → WAIT (sit out)
"""
import os, json, requests
import yfinance as yf
import numpy as np
from datetime import datetime, timezone, timedelta

CST = timedelta(hours=-6)

def cst(dt): return dt + CST
def prob_bar(p): return '█' * int(p/10) + '░' * (10 - int(p/10))
def now_utc(): return datetime.now(timezone.utc)

# ── DATA FETCH & ANALYSIS ──
def fetch_data():
    gold = yf.Ticker("GC=F")
    df = gold.history(period="3d", interval="5m")
    if df.empty:
        raise Exception("yfinance empty")

    df['SMA20']   = df['Close'].rolling(20).mean()
    df['STD20']   = df['Close'].rolling(20).std()
    df['Upper']   = df['SMA20'] + df['STD20'] * 2.0
    df['Lower']   = df['SMA20'] - df['STD20'] * 2.0
    df['TR']      = abs(df['High'] - df['Low'])
    df['ATR14']   = df['TR'].rolling(14).mean()
    df['ATR_avg'] = df['ATR14'].rolling(50).mean()
    df['UpMove']  = df['High'] - df['High'].shift(1)
    df['DnMove']  = df['Low'].shift(1) - df['Low']
    df['+DM']     = ((df['UpMove'] > df['DnMove']) & (df['UpMove'] > 0)) * df['UpMove']
    df['-DM']     = ((df['DnMove'] > df['UpMove']) & (df['DnMove'] > 0)) * df['DnMove']
    df['+DI']     = 100 * df['+DM'].rolling(14).mean() / df['ATR14']
    df['-DI']     = 100 * df['-DM'].rolling(14).mean() / df['ATR14']
    df['DX']      = 100 * abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])
    df['ADX']     = df['DX'].rolling(14).mean()
    df['ROC']     = df['Close'].pct_change(12) * 100
    df = df.dropna()

    row      = df.iloc[-1]
    price    = round(row['Close'], 2)
    upper    = round(row['Upper'], 2)
    lower    = round(row['Lower'], 2)
    adx      = row['ADX']
    atr_r    = row['ATR14'] / row['ATR_avg'] if row['ATR_avg'] > 0 else 1.0
    roc      = abs(row['ROC'])
    plus_di  = row['+DI']
    minus_di = row['-DI']

    # ── AUTO-MODE DETECTION (ADX + ATR + ROC) ──
    if adx > 25 and atr_r > 1.2 and roc > 0.3:
        mode = 'TREND'
    elif adx < 20 or atr_r < 0.8:
        mode = 'CONSOLIDATION'
    else:
        mode = 'TRANSITION'

    # ── SIGNAL LOGIC ──
    risk = 30.0 if mode == 'TREND' else 20.0

    if mode == 'CONSOLIDATION':
        if price < lower:
            signal, prob = 'BUY',  min(95, 75 + (lower - price) * 2)
        elif price > upper:
            signal, prob = 'SELL', min(95, 75 + (price - upper) * 2)
        else:
            dist = min(abs(price - upper), abs(price - lower))
            signal = 'PREPARE' if dist < 5 else 'WAIT'
            prob   = 65 if signal == 'PREPARE' else max(10, 50 - dist * 0.3)

    elif mode == 'TREND':
        if price > upper and plus_di > minus_di:
            signal, prob = 'BUY',  min(95, 75 + (price - upper) * 1.5)
        elif price < lower and minus_di > plus_di:
            signal, prob = 'SELL', min(95, 75 + (lower - price) * 1.5)
        else:
            signal, prob = 'WAIT', 30.0
    else:
        signal, prob = 'WAIT', 25.0

    return {
        'price': price, 'upper': upper, 'lower': lower,
        'signal': signal, 'probability': round(prob, 1),
        'mode': mode, 'adx': round(adx, 1), 'risk': risk
    }

# ── STATE FILE ──
STATE_FILE = 'pulse_state.json'

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {'active_signal': None, 'signal_time': None, 'signal_price': None,
                'countdown_step': 0, 'entry_mode': None}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# ── PULSE LOG ──
def save_log(data):
    entry = {
        'timestamp': cst(now_utc()).strftime('%Y-%m-%d %H:%M CST'),
        'price':       data['price'],
        'probability': data['probability'],
        'signal':      data['signal'],
        'mode':        data['mode'],
        'status':      'SIGNAL' if data['probability'] > 75 else data['signal']
    }
    try:
        with open('pulse_log.json') as f:
            logs = json.load(f)
    except:
        logs = []
    logs.append(entry)
    logs = logs[-100:]
    with open('pulse_log.json', 'w') as f:
        json.dump(logs, f, indent=2)

# ── DISCORD SEND ──
def send(webhook, embed):
    if not webhook:
        print("No webhook configured.")
        return
    r = requests.post(webhook, json={"embeds": [embed]},
                      headers={"Content-Type": "application/json"})
    print(f"Discord: {r.status_code}")

# ── EMBED BUILDERS ──
def embed_monitoring(data):
    """Regular WAIT/PREPARE monitoring pulse"""
    now = now_utc()
    nc  = cst(now)
    nxt = cst(now + timedelta(minutes=5))
    return {
        "title": "AURA-V 2.0 HYBRID | MONITORING",
        "color": 0x333333,
        "fields": [
            {"name": "MODE",        "value": f"```\n{data['mode']}\n```",                "inline": True},
            {"name": "SIGNAL",      "value": f"```\n{data['signal']}\n```",               "inline": True},
            {"name": "PRICE",       "value": f"```\n${data['price']}\n```",               "inline": True},
            {"name": "PROBABILITY", "value": f"```\n{data['probability']}%\n{prob_bar(data['probability'])}\n```", "inline": True},
            {"name": "ADX",         "value": f"```\n{data['adx']}\n```",                 "inline": True},
            {"name": "2.0 STD",     "value": f"```\nU: ${data['upper']}\nL: ${data['lower']}\n```", "inline": True},
            {"name": "TIME (CST)",  "value": f"```\n{nc.strftime('%H:%M CST')}\n```",    "inline": True},
            {"name": "NEXT PULSE",  "value": f"```\n{nxt.strftime('%H:%M CST')}\n```",   "inline": True},
        ],
        "timestamp": now.isoformat(),
        "footer": {"text": f"Hybrid Auto-Mode | {data['mode']} | 5-Min Pulse"}
    }

def embed_trend_immediate(data, entry_time_cst):
    """TREND mode — immediate entry alert"""
    color = 0x39d98a if data['signal'] == 'BUY' else 0xff5d5d
    risk  = data['risk']
    sp    = data['price']
    tgt   = round(sp + risk, 2) if data['signal'] == 'BUY' else round(sp - risk, 2)
    stp   = round(sp - risk, 2) if data['signal'] == 'BUY' else round(sp + risk, 2)
    return {
        "title": f"⚡ TREND SIGNAL — ENTER NOW | {data['signal']}",
        "description": "TREND MODE: High momentum detected. Enter immediately — do not wait.",
        "color": color,
        "fields": [
            {"name": "MODE",        "value": "```\nTREND — IMMEDIATE\n```",              "inline": True},
            {"name": "SIGNAL",      "value": f"```\n{data['signal']}\n```",               "inline": True},
            {"name": "PROBABILITY", "value": f"```\n{data['probability']}%\n{prob_bar(data['probability'])}\n```", "inline": True},
            {"name": "ENTRY PRICE", "value": f"```\n${sp}\n```",                          "inline": True},
            {"name": "TARGET",      "value": f"```\n${tgt} (+{risk} pts)\n```",           "inline": True},
            {"name": "STOP LOSS",   "value": f"```\n${stp} (-{risk} pts)\n```",           "inline": True},
            {"name": "ADX",         "value": f"```\n{data['adx']} (TRENDING)\n```",      "inline": True},
            {"name": "TIME (CST)",  "value": f"```\n{entry_time_cst}\n```",               "inline": True},
            {"name": "ACTION",      "value": "```\nOPEN CHART → CONFIRM BREAKOUT → ENTER MARKET\n```", "inline": False},
        ],
        "timestamp": now_utc().isoformat(),
        "footer": {"text": "TREND MODE: Immediate Entry | Hybrid Auto-Mode"}
    }

def embed_fifteen_sec(data, sp):
    """15-second final execution window"""
    color = 0x39d98a if data['signal'] == 'BUY' else 0xff5d5d
    risk  = data['risk']
    tgt   = round(sp + risk, 2) if data['signal'] == 'BUY' else round(sp - risk, 2)
    stp   = round(sp - risk, 2) if data['signal'] == 'BUY' else round(sp + risk, 2)
    return {
        "title": f"🟢 15 SECONDS — EXECUTE {data['signal']}",
        "description": "Final window. Open chart, confirm band, place order.",
        "color": color,
        "fields": [
            {"name": "ENTRY",  "value": f"```\n${sp}\n```",  "inline": True},
            {"name": "TARGET", "value": f"```\n${tgt}\n```", "inline": True},
            {"name": "STOP",   "value": f"```\n${stp}\n```", "inline": True},
            {"name": "WINDOW", "value": "```\n15 ▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌  0\n```", "inline": False},
            {"name": "ACTION", "value": "```\nCONFIRM PRICE AT BAND → ENTER MARKET\n```", "inline": False},
        ],
        "timestamp": now_utc().isoformat(),
        "footer": {"text": "15-Second Entry Window | CONSOLIDATION Mode"}
    }

def embed_countdown(data, step, entry_time_cst, sp):
    """CONSOLIDATION countdown steps: 4=20min, 3=15min, 2=10min, 1=5min, 0=ENTER"""
    color = 0x39d98a if data['signal'] == 'BUY' else 0xff5d5d
    risk  = data['risk']
    tgt   = round(sp + risk, 2) if data['signal'] == 'BUY' else round(sp - risk, 2)
    stp   = round(sp - risk, 2) if data['signal'] == 'BUY' else round(sp + risk, 2)

    labels = {4: ('🔔', '20 MIN WARNING',   'Signal confirmed. Begin preparation.'),
              3: ('⏳', '15 MIN REMAINING', 'Locate entry level on chart.'),
              2: ('⚠️', '10 MIN REMAINING', 'Confirm price still at band.'),
              1: ('🔴', '5 MIN REMAINING',  'Final position sizing check.'),
              0: ('🟢', 'ENTER NOW',        'Execute consolidation entry at band.')}
    emoji, label, desc = labels.get(step, ('📡', 'SIGNAL', ''))

    return {
        "title": f"CONSOL {emoji} {label} — {data['signal']}",
        "description": desc,
        "color": color,
        "fields": [
            {"name": "MODE",        "value": "```\nCONSOLIDATION — 20-MIN FILTER\n```",  "inline": True},
            {"name": "SIGNAL",      "value": f"```\n{data['signal']}\n```",                "inline": True},
            {"name": "PROBABILITY", "value": f"```\n{data['probability']}%\n{prob_bar(data['probability'])}\n```", "inline": True},
            {"name": "ENTRY PRICE", "value": f"```\n${sp}\n```",                           "inline": True},
            {"name": "TARGET",      "value": f"```\n${tgt} (+{risk} pts)\n```",            "inline": True},
            {"name": "STOP LOSS",   "value": f"```\n${stp} (-{risk} pts)\n```",            "inline": True},
            {"name": "SIGNAL TIME", "value": f"```\n{entry_time_cst}\n```",                "inline": True},
            {"name": "STEP",        "value": f"```\n{5 - step} of 5\n```",                "inline": True},
        ],
        "timestamp": now_utc().isoformat(),
        "footer": {"text": f"CONSOLIDATION Mode: 20-Min Confirmation Filter | Step {5-step}/5"}
    }

# ── MAIN ──
def main():
    print("Aura-V 2.0 Hybrid Pulse starting...")
    data    = fetch_data()
    state   = load_state()
    webhook = os.environ.get('DISCORD_WEBHOOK_ALERTS')
    now_cst_str = cst(now_utc()).strftime('%H:%M CST')

    high_conviction = data['signal'] in ('BUY', 'SELL') and data['probability'] > 75

    print(f"Mode: {data['mode']} | Signal: {data['signal']} @ {data['probability']}% | Price: ${data['price']}")

    if high_conviction:
        if data['mode'] == 'TREND':
            # ── TREND: IMMEDIATE ENTRY ──
            # Only fire if not already in a trend signal for same direction
            if state.get('active_signal') != f"TREND_{data['signal']}":
                state = {
                    'active_signal': f"TREND_{data['signal']}",
                    'signal_time': now_cst_str,
                    'signal_price': data['price'],
                    'countdown_step': 0,
                    'entry_mode': 'TREND'
                }
                print(f"TREND IMMEDIATE: {data['signal']} @ ${data['price']}")
                send(webhook, embed_trend_immediate(data, now_cst_str))
            else:
                # Already alerted this trend — send monitoring pulse
                send(webhook, embed_monitoring(data))

        elif data['mode'] == 'CONSOLIDATION':
            # ── CONSOLIDATION: 20-MIN COUNTDOWN ──
            prev_signal = state.get('active_signal')
            prev_mode   = state.get('entry_mode')

            if prev_signal != data['signal'] or prev_mode != 'CONSOLIDATION':
                # NEW consolidation signal — start countdown at step 4 (20 min)
                state = {
                    'active_signal': data['signal'],
                    'signal_time': now_cst_str,
                    'signal_price': data['price'],
                    'countdown_step': 4,
                    'entry_mode': 'CONSOLIDATION'
                }
                print(f"CONSOL NEW: {data['signal']} @ ${data['price']} — Step 4 (20 min)")
                send(webhook, embed_countdown(data, 4, now_cst_str, data['price']))
            else:
                # CONTINUING — decrement step
                step = max(0, state['countdown_step'] - 1)
                state['countdown_step'] = step
                sp   = state['signal_price']
                print(f"CONSOL Step: {step}")
                send(webhook, embed_countdown(data, step, state['signal_time'], sp))

                if step == 0:
                    # Fire 15-second window immediately after ENTER NOW
                    send(webhook, embed_fifteen_sec(data, sp))
                    # Reset state
                    state = {'active_signal': None, 'signal_time': None,
                             'signal_price': None, 'countdown_step': 0, 'entry_mode': None}
        else:
            # TRANSITION with high prob — monitor only
            state = {'active_signal': None, 'signal_time': None,
                     'signal_price': None, 'countdown_step': 0, 'entry_mode': None}
            send(webhook, embed_monitoring(data))
    else:
        # No signal — reset any stale trend state, keep consol countdown if active
        if state.get('entry_mode') == 'TREND':
            state = {'active_signal': None, 'signal_time': None,
                     'signal_price': None, 'countdown_step': 0, 'entry_mode': None}
        send(webhook, embed_monitoring(data))

    save_state(state)
    save_log(data)
    print("Done.")

if __name__ == "__main__":
    main()
