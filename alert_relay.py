#!/usr/bin/env python3
"""
Aura-V 2.0 Pulse Relay — AUTO-MODE + 20/15/10/5/ENTER Countdown
"""
import os, json, requests, statistics
import yfinance as yf
from datetime import datetime, timezone, timedelta

CST_OFFSET = timedelta(hours=-6)

def cst(dt): return dt + CST_OFFSET
def prob_bar(p): return '█' * int(p/10) + '░' * (10 - int(p/10))

# ── DATA FETCH ──
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

    row = df.iloc[-1]
    price  = round(row['Close'], 2)
    upper  = round(row['Upper'], 2)
    lower  = round(row['Lower'], 2)
    adx    = row['ADX']
    atr_r  = row['ATR14'] / row['ATR_avg'] if row['ATR_avg'] > 0 else 1.0
    roc    = abs(row['ROC'])
    plus_di  = row['+DI']
    minus_di = row['-DI']

    # ── AUTO-MODE DETECTION ──
    if adx > 25 and atr_r > 1.2 and roc > 0.3:
        mode = 'TREND'
    elif adx < 20 or atr_r < 0.8:
        mode = 'CONSOLIDATION'
    else:
        mode = 'TRANSITION'

    # ── SIGNAL ──
    if mode == 'CONSOLIDATION':
        if price < lower:
            signal, prob = 'BUY', min(95, 75 + (lower - price) * 2)
        elif price > upper:
            signal, prob = 'SELL', min(95, 75 + (price - upper) * 2)
        else:
            dist = min(abs(price - upper), abs(price - lower))
            signal = 'PREPARE' if dist < 5 else 'WAIT'
            prob = 65 if signal == 'PREPARE' else max(10, 50 - dist * 0.3)

    elif mode == 'TREND':
        if price > upper and plus_di > minus_di:
            signal, prob = 'BUY', min(95, 75 + (price - upper) * 1.5)
        elif price < lower and minus_di > plus_di:
            signal, prob = 'SELL', min(95, 75 + (lower - price) * 1.5)
        else:
            signal, prob = 'WAIT', 30.0
    else:
        signal, prob = 'WAIT', 25.0

    risk = 30.0 if mode == 'TREND' else 20.0
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
        return {'active_signal': None, 'signal_time': None, 'signal_price': None, 'countdown_step': 0}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# ── DISCORD SEND ──
def send(webhook, embed):
    if not webhook: return
    r = requests.post(webhook, json={"embeds": [embed]}, headers={"Content-Type": "application/json"})
    print(f"Sent: {r.status_code}")

# ── EMBED BUILDERS ──
def embed_alert(data, step, entry_time_cst):
    colors = {'BUY': 0x39d98a, 'SELL': 0xff5d5d}
    color = colors.get(data['signal'], 0xf6c453)

    step_labels = {4: '20 MIN WARNING', 3: '15 MIN REMAINING', 2: '10 MIN REMAINING', 1: '5 MIN REMAINING', 0: 'ENTER NOW'}
    step_emojis = {4: '🔔', 3: '⏳', 2: '⚠️', 1: '🔴', 0: '🟢'}
    label = step_labels.get(step, 'SIGNAL')
    emoji = step_emojis.get(step, '📡')

    risk = data['risk']
    if data['signal'] == 'BUY':
        target = round(data['signal_price'] + risk, 2)
        stop   = round(data['signal_price'] - risk, 2)
    else:
        target = round(data['signal_price'] - risk, 2)
        stop   = round(data['signal_price'] + risk, 2)

    if step == 0:
        title = f"ENTER NOW — {data['signal']}"
        desc  = f"Execute your {data['signal']} trade at market price"
    else:
        title = f"{emoji} {label} — {data['signal']} SIGNAL"
        desc  = f"Prepare your {data['signal']} entry. Countdown in progress."

    fields = [
        {"name": "MODE",        "value": f"```\n{data['mode']}\n```",               "inline": True},
        {"name": "SIGNAL",      "value": f"```\n{data['signal']}\n```",              "inline": True},
        {"name": "PROBABILITY", "value": f"```\n{data['probability']}%\n{prob_bar(data['probability'])}\n```", "inline": True},
        {"name": "ENTRY PRICE", "value": f"```\n${data['signal_price']}\n```",       "inline": True},
        {"name": "TARGET",      "value": f"```\n${target} (+{risk} pts)\n```",       "inline": True},
        {"name": "STOP LOSS",   "value": f"```\n${stop} (-{risk} pts)\n```",         "inline": True},
        {"name": "SIGNAL TIME", "value": f"```\n{entry_time_cst}\n```",              "inline": True},
        {"name": "STEP",        "value": f"```\n{5 - step} of 5\n```",              "inline": True},
    ]

    if step == 0:
        fields.append({"name": "ACTION", "value": "```\nOPEN CHART → CONFIRM BAND → EXECUTE\n```", "inline": False})

    now_utc = datetime.now(timezone.utc)
    return {
        "title": f"AURA-V 2.0 | {title}",
        "description": desc,
        "color": color,
        "fields": fields,
        "timestamp": now_utc.isoformat(),
        "footer": {"text": f"Auto-Mode: {data['mode']} | ADX: {data['adx']} | 5-Min Pulse"}
    }

def embed_pulse(data):
    """Regular monitoring pulse — no active signal"""
    now_utc = datetime.now(timezone.utc)
    now_cst = cst(now_utc)
    next_cst = cst(now_utc + timedelta(minutes=5))
    color = 0x888888

    return {
        "title": "AURA-V 2.0 PULSE",
        "color": color,
        "fields": [
            {"name": "MODE",        "value": f"```\n{data['mode']}\n```",              "inline": True},
            {"name": "SIGNAL",      "value": f"```\n{data['signal']}\n```",             "inline": True},
            {"name": "PRICE",       "value": f"```\n${data['price']}\n```",             "inline": True},
            {"name": "PROBABILITY", "value": f"```\n{data['probability']}%\n{prob_bar(data['probability'])}\n```", "inline": True},
            {"name": "ADX",         "value": f"```\n{data['adx']}\n```",               "inline": True},
            {"name": "2.0 STD BANDS", "value": f"```\nUpper: ${data['upper']}\nLower: ${data['lower']}\n```", "inline": False},
            {"name": "TIME (CST)",  "value": f"```\n{now_cst.strftime('%H:%M CST')}\n```",  "inline": True},
            {"name": "NEXT PULSE",  "value": f"```\n{next_cst.strftime('%H:%M CST')}\n```", "inline": True},
        ],
        "timestamp": now_utc.isoformat(),
        "footer": {"text": f"Auto-Mode Active | 5-Min Pulse"}
    }

# ── SAVE PULSE LOG ──
def save_log(data):
    entry = {
        "timestamp": cst(datetime.now(timezone.utc)).strftime('%Y-%m-%d %H:%M CST'),
        "price": data['price'],
        "probability": data['probability'],
        "signal": data['signal'],
        "mode": data['mode'],
        "status": "STAGE 1 TRIGGER" if data['probability'] > 75 else data['signal']
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

# ── MAIN ──
def main():
    print("Pulse starting...")
    data = fetch_data()
    state = load_state()
    webhook = os.environ.get('DISCORD_WEBHOOK_ALERTS')
    
    now_utc = datetime.now(timezone.utc)
    now_cst = cst(now_utc)

    high_conviction = data['signal'] in ('BUY', 'SELL') and data['probability'] > 75

    if high_conviction:
        if state['active_signal'] != data['signal'] or state.get('signal_price') is None:
            # NEW signal — start countdown from step 4 (20 min warning)
            state = {
                'active_signal': data['signal'],
                'signal_time': now_cst.strftime('%H:%M CST'),
                'signal_price': data['price'],
                'countdown_step': 4
            }
            data['signal_price'] = data['price']
            print(f"NEW signal: {data['signal']} @ ${data['price']} — Step 4 (20 min)")
            send(webhook, embed_alert({**data, 'signal_price': state['signal_price']}, 4, state['signal_time']))
        else:
            # CONTINUING signal — decrement countdown
            step = max(0, state['countdown_step'] - 1)
            state['countdown_step'] = step
            data['signal_price'] = state['signal_price']
            print(f"Countdown step: {step} ({['ENTER NOW','5 MIN','10 MIN','15 MIN','20 MIN'][step]})")
            send(webhook, embed_alert({**data, 'signal_price': state['signal_price']}, step, state['signal_time']))
            if step == 0:
                # Reset after ENTER NOW fires
                state = {'active_signal': None, 'signal_time': None, 'signal_price': None, 'countdown_step': 0}
    else:
        # No signal — send regular pulse, reset state
        state = {'active_signal': None, 'signal_time': None, 'signal_price': None, 'countdown_step': 0}
        send(webhook, embed_pulse(data))

    save_state(state)
    save_log(data)
    print(f"Mode: {data['mode']} | Signal: {data['signal']} @ {data['probability']}%")
    print("Done")

if __name__ == "__main__":
    main()
