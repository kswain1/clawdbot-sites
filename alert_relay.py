#!/usr/bin/env python3
"""
Aura-V Multi-Strategy Relay
Runs 3 strategies simultaneously — each with its own log, state, trade tracker, and alerts.

STRATEGIES:
  HYBRID    — Original Hybrid Auto-Mode (baseline, high frequency)
  VELOCITY  — Optimized for fastest prop firm passes (rr=4.5, min_prob=0.25)
  CHALLENGE — Optimized for max pass rate (rr=4.5, min_prob=0.42, bb_std=2.5)
"""
import os, json, requests, sys
import yfinance as yf
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta

CST = timedelta(hours=-6)
def cst(dt): return dt + CST
def now_utc(): return datetime.now(timezone.utc)
def prob_bar(p): return '█' * int(p/10) + '░' * (10 - int(p/10))

# ── STRATEGY CONFIGS ──────────────────────────────────────────────────────────
STRATEGIES = {
    'HYBRID': {
        'name':        'Hybrid Auto-Mode',
        'short':       'HYBRID',
        'emoji':       '🤖',
        'bb_period':   20,
        'bb_std':      2.0,
        'rr':          2.8,
        'min_prob':    0.0,     # no gate — fires on any conviction
        'entry_hours': list(range(24)),   # any hour
        'risk':        20.0,
        'htf_bars':    0,       # no HTF filter
        'protect_at':  0.07,
        'color_buy':   0x39d98a,
        'color_sell':  0xff5d5d,
        'color_wait':  0x333333,
        'webhook_env': 'DISCORD_WEBHOOK_ALERTS',
        'state_file':  'state_hybrid.json',
        'pulse_log':   'pulse_log.json',             # keep original name for site compat
        'trade_log':   'trade_log_hybrid.json',
        'trade_state': 'trade_state_hybrid.json',
    },
    'VELOCITY': {
        'name':        'Velocity Mode',
        'short':       'VELOCITY',
        'emoji':       '⚡',
        'bb_period':   16,
        'bb_std':      2.0,
        'rr':          4.5,
        'min_prob':    0.25,
        'entry_hours': [8, 9, 10, 18, 19, 20],
        'risk':        20.0,
        'htf_bars':    48,
        'protect_at':  0.06,
        'color_buy':   0xf6c453,
        'color_sell':  0xff8c00,
        'color_wait':  0x2a2000,
        'webhook_env': 'DISCORD_WEBHOOK_VELOCITY',
        'state_file':  'state_velocity.json',
        'pulse_log':   'pulse_log_velocity.json',
        'trade_log':   'trade_log_velocity.json',
        'trade_state': 'trade_state_velocity.json',
    },
    'CHALLENGE': {
        'name':        'Challenge Mode',
        'short':       'CHALLENGE',
        'emoji':       '🛡️',
        'bb_period':   20,
        'bb_std':      2.5,
        'rr':          4.5,
        'min_prob':    0.42,
        'entry_hours': [8, 9, 18, 19, 20],
        'risk':        20.0,
        'htf_bars':    48,
        'protect_at':  0.07,
        'color_buy':   0x6ab8ff,
        'color_sell':  0xb06aff,
        'color_wait':  0x0a0f18,
        'webhook_env': 'DISCORD_WEBHOOK_CHALLENGE',
        'state_file':  'state_challenge.json',
        'pulse_log':   'pulse_log_challenge.json',
        'trade_log':   'trade_log_challenge.json',
        'trade_state': 'trade_state_challenge.json',
    },
}

# ── WEBHOOKS (fallback chain) ─────────────────────────────────────────────────
WEBHOOK_ALERTS    = os.environ.get('DISCORD_WEBHOOK_ALERTS', '')
WEBHOOK_VELOCITY  = os.environ.get('DISCORD_WEBHOOK_VELOCITY',  WEBHOOK_ALERTS)
WEBHOOK_CHALLENGE = os.environ.get('DISCORD_WEBHOOK_CHALLENGE', WEBHOOK_ALERTS)

WEBHOOK_MAP = {
    'HYBRID':    WEBHOOK_ALERTS,
    'VELOCITY':  WEBHOOK_VELOCITY,
    'CHALLENGE': WEBHOOK_CHALLENGE,
}

# ── DATA FETCH ────────────────────────────────────────────────────────────────
def fetch_raw():
    """Returns raw OHLCV df + last row indicators."""
    gold = yf.Ticker("GC=F")
    df = gold.history(period="5d", interval="5m")
    if df.empty: raise Exception("yfinance empty")
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
    return df

def get_htf_bias(closes, htf_bars):
    """Simple HTF bias: above/below SMA of last htf_bars bars."""
    if htf_bars == 0 or len(closes) < htf_bars: return 'NEUTRAL'
    sma = np.mean(closes[-htf_bars:])
    cur = closes[-1]
    if cur > sma * 1.001: return 'BULL'
    if cur < sma * 0.999: return 'BEAR'
    return 'NEUTRAL'

def analyze(df, cfg):
    """Apply strategy config to dataframe, return signal data."""
    bp = cfg['bb_period']
    bs = cfg['bb_std']
    rr = cfg['rr']
    risk = cfg['risk']
    htf  = cfg['htf_bars']
    mp   = cfg['min_prob']
    eh   = cfg['entry_hours']

    closes = df['Close'].values.tolist()
    sma    = np.mean(closes[-bp:])
    std    = np.std(closes[-bp:], ddof=1)
    upper  = round(sma + bs * std, 2)
    lower  = round(sma - bs * std, 2)

    row      = df.iloc[-1]
    price    = round(row['Close'], 2)
    adx      = row['ADX']
    atr_r    = row['ATR14'] / row['ATR_avg'] if row['ATR_avg'] > 0 else 1.0
    roc      = abs(row['ROC'])
    plus_di  = row['+DI']
    minus_di = row['-DI']

    now_cst  = cst(now_utc())
    hour     = now_cst.hour

    # ── AUTO-MODE ──
    if adx > 25 and atr_r > 1.2 and roc > 0.3:
        mode = 'TREND'
    elif adx < 20 or atr_r < 0.8:
        mode = 'CONSOLIDATION'
    else:
        mode = 'TRANSITION'

    # ── HTF BIAS ──
    bias = get_htf_bias(closes, htf)

    # ── SIGNAL LOGIC ──
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

    prob = round(prob, 1)

    # ── FILTERS ──
    filtered = False
    filter_reason = ''
    if signal in ('BUY', 'SELL'):
        if hour not in eh:
            filtered = True; filter_reason = f'off-hours ({hour}:xx CST)'
        elif prob < mp * 100 and mp > 0:
            filtered = True; filter_reason = f'prob {prob}% < min {mp*100:.0f}%'
        elif bias != 'NEUTRAL':
            if (signal == 'BUY' and bias == 'BEAR') or (signal == 'SELL' and bias == 'BULL'):
                filtered = True; filter_reason = f'HTF contra ({bias})'

    if filtered:
        signal = 'FILTERED'

    return {
        'price': price, 'upper': upper, 'lower': lower,
        'signal': signal, 'probability': prob,
        'mode': mode, 'adx': round(adx, 1), 'risk': risk,
        'rr': rr, 'bias': bias, 'hour': hour,
        'filtered': filtered, 'filter_reason': filter_reason,
    }

# ── STATE & LOG ───────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path) as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=2)

def save_pulse_log(cfg, data):
    logs = load_json(cfg['pulse_log'], [])
    logs.append({
        'timestamp': cst(now_utc()).strftime('%Y-%m-%d %H:%M CST'),
        'strategy':  cfg['short'],
        'price':     data['price'],
        'probability': data['probability'],
        'signal':    data['signal'],
        'mode':      data['mode'],
        'bias':      data['bias'],
    })
    save_json(cfg['pulse_log'], logs[-200:])

# ── DISCORD ───────────────────────────────────────────────────────────────────
def send(webhook, embed):
    if not webhook: return
    try:
        r = requests.post(webhook, json={"embeds": [embed]},
                          headers={"Content-Type": "application/json"}, timeout=10)
        print(f"  Discord [{r.status_code}]")
    except Exception as e:
        print(f"  Discord error: {e}")

# ── EMBED BUILDERS ────────────────────────────────────────────────────────────
def footer(cfg, extra=''):
    return {"text": f"{cfg['emoji']} {cfg['name'].upper()} | Aura-V | 5-Min Pulse{' | ' + extra if extra else ''}"}

def embed_monitoring(cfg, data):
    now = now_utc(); nc = cst(now); nxt = cst(now + timedelta(minutes=5))
    color = cfg['color_wait']
    if data['signal'] == 'BUY':    color = cfg['color_buy']
    elif data['signal'] == 'SELL': color = cfg['color_sell']
    fields = [
        {"name": "STRATEGY",    "value": f"```\n{cfg['emoji']} {cfg['name']}\n```",     "inline": True},
        {"name": "MODE",        "value": f"```\n{data['mode']}\n```",                   "inline": True},
        {"name": "SIGNAL",      "value": f"```\n{data['signal']}\n```",                 "inline": True},
        {"name": "PRICE",       "value": f"```\n${data['price']}\n```",                 "inline": True},
        {"name": "PROBABILITY", "value": f"```\n{data['probability']}%\n{prob_bar(data['probability'])}\n```", "inline": True},
        {"name": "ADX",         "value": f"```\n{data['adx']}\n```",                   "inline": True},
        {"name": f"{cfg['bb_std']}σ BANDS",  "value": f"```\nU: ${data['upper']}\nL: ${data['lower']}\n```", "inline": True},
        {"name": "HTF BIAS",    "value": f"```\n{data['bias']}\n```",                   "inline": True},
        {"name": "NEXT PULSE",  "value": f"```\n{nxt.strftime('%H:%M CST')}\n```",      "inline": True},
    ]
    if data['filtered']:
        fields.append({"name": "⚠️ FILTERED", "value": f"```\n{data['filter_reason']}\n```", "inline": False})
    return {
        "title": f"{cfg['emoji']} {cfg['name']} | MONITORING",
        "color": color, "fields": fields,
        "timestamp": now.isoformat(),
        "footer": footer(cfg, data['mode'])
    }

def embed_signal(cfg, data, label, desc, step_label='', enter_now=False):
    color = cfg['color_buy'] if data['signal'] == 'BUY' else cfg['color_sell']
    risk  = data['risk']; rr = data['rr']; sp = data['price']
    tgt   = round(sp + risk * rr, 2) if data['signal'] == 'BUY' else round(sp - risk * rr, 2)
    stp   = round(sp - risk, 2)      if data['signal'] == 'BUY' else round(sp + risk, 2)
    prob  = data['probability']
    bias  = data['bias']
    mode  = data['mode']
    sig   = data['signal']
    min_p = cfg.get('min_prob', 0.0) * 100   # convert to percentage
    htf   = cfg.get('htf_bars', 0)
    entry_hours = cfg.get('entry_hours', list(range(24)))
    cur_hour = cst(now_utc()).hour

    # ── Signal Quality Gate Checks ──────────────────────────────────────────
    gate_prob    = prob >= min_p
    gate_htf     = (htf == 0) or (bias in ('BULLISH', 'BEARISH') and
                    ((sig == 'BUY' and bias == 'BULLISH') or (sig == 'SELL' and bias == 'BEARISH')))
    gate_hours   = cur_hour in entry_hours
    gate_mode    = mode in ('TREND', 'CONSOL', 'RANGING')
    gate_rr      = rr >= 2.8
    gates_passed = sum([gate_prob, gate_htf, gate_hours, gate_mode, gate_rr])
    gates_total  = 5

    def ck(v): return '✅' if v else '❌'

    # Gate scorecard as a compact block
    ck_p  = '✅' if gate_prob  else '❌'
    ck_h  = '✅' if gate_htf   else '❌'
    ck_hr = '✅' if gate_hours else '❌'
    ck_m  = '✅' if gate_mode  else '❌'
    ck_r  = '✅' if gate_rr    else '❌'
    ck_s  = '✅' if gates_passed == gates_total else '⚠️'
    prob_cmp = '>=' if gate_prob  else '<'
    htf_txt  = 'aligned'   if gate_htf   else 'MISALIGNED'
    hr_txt   = 'in window' if gate_hours else 'OUTSIDE window'
    rr_txt   = '>= min'    if gate_rr    else 'BELOW min'
    scorecard = (
        f"{ck_p}  Probability  {prob:.1f}% {prob_cmp} {min_p:.0f}% threshold\n"
        f"{ck_h}  HTF Bias     {bias} ({htf_txt})\n"
        f"{ck_hr}  Entry Hour   {cur_hour}:00 CST ({hr_txt})\n"
        f"{ck_m}  Market Mode  {mode}\n"
        f"{ck_r}  R:R Ratio    1:{rr} ({rr_txt})\n"
        f"─────────────────────────────\n"
        f"{ck_s}  Score: {gates_passed}/{gates_total} gates passed"
    )

    title = f"{'🟢 ENTER NOW' if enter_now else label} — {cfg['emoji']} {cfg['name']} | {sig}"

    fields = [
        {"name": "ENTRY",   "value": f"```\n${sp}\n```",                              "inline": True},
        {"name": "TARGET",  "value": f"```\n${tgt}  +{round(risk*rr,1)} pts\n```",   "inline": True},
        {"name": "STOP",    "value": f"```\n${stp}  -{risk:.0f} pts\n```",            "inline": True},
        {"name": "R:R",     "value": f"```\n1:{rr}\n```",                             "inline": True},
        {"name": "MODE",    "value": f"```\n{mode}\n```",                              "inline": True},
        {"name": "PROB",    "value": f"```\n{prob:.1f}%  {prob_bar(prob)}\n```",      "inline": True},
        {"name": f"🔍 SIGNAL QUALITY — {gates_passed}/{gates_total}", 
         "value": f"```\n{scorecard}\n```", "inline": False},
    ]
    if step_label:
        fields.append({"name": "STEP",   "value": f"```\n{step_label}\n```", "inline": True})
    if desc:
        fields.append({"name": "ACTION", "value": f"```\n{desc}\n```",       "inline": False})

    return {
        "title": title, "color": color, "fields": fields,
        "timestamp": now_utc().isoformat(),
        "footer": footer(cfg, 'ENTER NOW' if enter_now else label)
    }

# ── TRADE LOGGER (inline, no import dependency) ───────────────────────────────
RISK_PTS  = 20.0
CONTRACT  = 10.0
DAILY_CAP = 400.0
TIMEOUT_M = 120
TRADE_WH  = os.environ.get('DISCORD_WEBHOOK_TRADE_LOG', '')

def trade_open(cfg, signal, price, prob, rr):
    state = load_json(cfg['trade_state'], {'open': None, 'next_id': 1, 'daily': {}})
    if state.get('open'): return  # already open
    today = cst(now_utc()).strftime('%Y-%m-%d')
    daily_pnl = state.get('daily', {}).get(today, {}).get('pnl', 0.0)
    if daily_pnl <= -DAILY_CAP: print(f"  [{cfg['short']}] daily cap hit"); return
    n = state.get('next_id', 1); state['next_id'] = n + 1
    tid = f"{cfg['short'][0]}{n:03d}"
    target = round(price + RISK_PTS * rr, 2) if signal == 'BUY' else round(price - RISK_PTS * rr, 2)
    stop   = round(price - RISK_PTS, 2)      if signal == 'BUY' else round(price + RISK_PTS, 2)
    trade  = {'id': tid, 'opened_at': cst(now_utc()).strftime('%Y-%m-%d %H:%M CST'),
              'opened_utc': now_utc().isoformat(), 'signal': signal, 'strategy': cfg['short'],
              'entry': price, 'target': target, 'stop': stop, 'rr': rr,
              'probability': prob, 'result': 'OPEN'}
    state['open'] = trade
    save_json(cfg['trade_state'], state)
    log = load_json(cfg['trade_log'], [])
    log.append(trade); save_json(cfg['trade_log'], log[-200:])
    print(f"  [{cfg['short']}] TRADE OPEN: {tid} {signal} @ ${price} tgt=${target} stp=${stop}")
    send(TRADE_WH, {
        "title": f"📋 {cfg['emoji']} {cfg['name']} — TRADE OPENED {signal} #{tid}",
        "color": 0x39d98a if signal=='BUY' else 0xff5d5d,
        "fields": [
            {"name":"STRATEGY","value":f"```\n{cfg['emoji']} {cfg['name']}\n```","inline":True},
            {"name":"ENTRY",   "value":f"```\n${price}\n```","inline":True},
            {"name":"TARGET",  "value":f"```\n${target}\n```","inline":True},
            {"name":"STOP",    "value":f"```\n${stop}\n```","inline":True},
            {"name":"R:R",     "value":f"```\n1:{rr}\n```","inline":True},
            {"name":"PROB",    "value":f"```\n{prob}%\n```","inline":True},
        ],
        "timestamp": now_utc().isoformat(),
        "footer": {"text": f"{cfg['name']} | Paper Trade"}
    })

def trade_check(cfg, current_price):
    state = load_json(cfg['trade_state'], {'open': None, 'next_id': 1, 'daily': {}})
    trade = state.get('open')
    if not trade or trade.get('result') != 'OPEN': return
    signal=trade['signal']; target=trade['target']; stop=trade['stop']
    opened=datetime.fromisoformat(trade['opened_utc']); hold_min=int((now_utc()-opened).total_seconds()/60)
    hit_t=(signal=='BUY' and current_price>=target) or (signal=='SELL' and current_price<=target)
    hit_s=(signal=='BUY' and current_price<=stop)   or (signal=='SELL' and current_price>=stop)
    timed=hold_min>=TIMEOUT_M
    if not (hit_t or hit_s or timed): return
    exit_p = target if hit_t else (stop if hit_s else current_price)
    reason = 'TARGET' if hit_t else ('STOP' if hit_s else 'TIMEOUT')
    pnl_pts = (exit_p-trade['entry']) if signal=='BUY' else (trade['entry']-exit_p)
    pnl_usd = round(pnl_pts*CONTRACT, 2)
    result  = 'WIN' if pnl_pts > 0 else 'LOSS'
    trade.update({'closed_at':cst(now_utc()).strftime('%Y-%m-%d %H:%M CST'),'hold_min':hold_min,
                  'exit':exit_p,'exit_reason':reason,'pnl_pts':round(pnl_pts,2),'pnl_usd':pnl_usd,'result':result})
    state['open'] = None
    today=cst(now_utc()).strftime('%Y-%m-%d'); d=state.setdefault('daily',{}).setdefault(today,{'wins':0,'losses':0,'pnl':0.0})
    if result=='WIN': d['wins']+=1
    else: d['losses']+=1
    d['pnl']=round(d['pnl']+pnl_usd,2)
    save_json(cfg['trade_state'], state)
    log=load_json(cfg['trade_log'],[]); 
    for i,t in enumerate(log):
        if t.get('id')==trade['id']: log[i]=trade; break
    save_json(cfg['trade_log'], log)
    print(f"  [{cfg['short']}] TRADE CLOSE: #{trade['id']} {result} | {reason} exit=${exit_p} pnl=${pnl_usd:+.2f} | {hold_min}min")
    send(TRADE_WH, {
        "title": f"{'✅' if result=='WIN' else '❌'} {cfg['emoji']} {cfg['name']} — {result} #{trade['id']}",
        "color": 0x39d98a if result=='WIN' else 0xff5d5d,
        "fields": [
            {"name":"STRATEGY",   "value":f"```\n{cfg['emoji']} {cfg['name']}\n```","inline":True},
            {"name":"EXIT REASON","value":f"```\n{reason}\n```","inline":True},
            {"name":"P&L (USD)",  "value":f"```\n${pnl_usd:+.2f}\n```","inline":True},
            {"name":"P&L (pts)",  "value":f"```\n{pnl_pts:+.1f}\n```","inline":True},
            {"name":"HOLD TIME",  "value":f"```\n{hold_min}m\n```","inline":True},
            {"name":"ENTRY→EXIT", "value":f"```\n${trade['entry']} → ${exit_p}\n```","inline":True},
        ],
        "timestamp": now_utc().isoformat(),
        "footer": {"text": f"{cfg['name']} | Paper Trade"}
    })

# ── STRATEGY RUNNER ───────────────────────────────────────────────────────────
def run_strategy(cfg_key, df):
    cfg    = STRATEGIES[cfg_key]
    wh     = WEBHOOK_MAP[cfg_key]
    data   = analyze(df, cfg)
    state  = load_json(cfg['state_file'], {'active_signal':None,'signal_time':None,'signal_price':None,'countdown_step':0,'entry_mode':None})
    now_cst_str = cst(now_utc()).strftime('%H:%M CST')

    print(f"\n[{cfg['short']}] mode={data['mode']} signal={data['signal']} prob={data['probability']}% price=${data['price']}")

    # Always check if open trade needs closing
    trade_check(cfg, data['price'])

    active = data['signal'] in ('BUY','SELL') and not data['filtered']
    high_q = data['probability'] > 75 and active

    if high_q:
        mode = data['mode']
        if mode == 'TREND':
            prev = state.get('active_signal')
            if prev != f"TREND_{data['signal']}":
                state = {'active_signal':f"TREND_{data['signal']}",'signal_time':now_cst_str,
                         'signal_price':data['price'],'countdown_step':3,'entry_mode':'TREND'}
                send(wh, embed_signal(cfg, data, '🔔 TREND 15 MIN WARNING', 'Signal locked. Prepare chart.', 'Step 1/4'))
            else:
                step = max(0, state['countdown_step'] - 1)
                state['countdown_step'] = step
                sp = state['signal_price']
                labels = {2:('⏳ TREND 10 MIN','Confirm price at band.','Step 2/4'),
                          1:('🔴 TREND 5 MIN', 'Final sizing check.','Step 3/4'),
                          0:('🟢 ENTER NOW',   'Execute entry now.','Step 4/4')}
                lbl, desc, sl = labels.get(step, ('📡 TREND','Monitoring.',''))
                d2 = dict(data); d2['price'] = sp
                send(wh, embed_signal(cfg, d2, lbl, desc, sl, enter_now=(step==0)))
                if step == 0:
                    trade_open(cfg, data['signal'], sp, data['probability'], cfg['rr'])
                    state = {'active_signal':None,'signal_time':None,'signal_price':None,'countdown_step':0,'entry_mode':None}

        elif mode == 'CONSOLIDATION':
            prev = state.get('active_signal')
            if prev != data['signal'] or state.get('entry_mode') != 'CONSOLIDATION':
                state = {'active_signal':data['signal'],'signal_time':now_cst_str,
                         'signal_price':data['price'],'countdown_step':4,'entry_mode':'CONSOLIDATION'}
                send(wh, embed_signal(cfg, data, '🔔 CONSOL 20 MIN WARNING', 'Signal confirmed. Begin prep.', 'Step 1/5'))
            else:
                step = max(0, state['countdown_step'] - 1)
                state['countdown_step'] = step
                sp = state['signal_price']
                labels = {3:('⏳ CONSOL 15 MIN','Locate entry on chart.','Step 2/5'),
                          2:('⚠️ CONSOL 10 MIN','Confirm price at band.','Step 3/5'),
                          1:('🔴 CONSOL 5 MIN', 'Final sizing check.','Step 4/5'),
                          0:('🟢 ENTER NOW',    'Execute entry at band.','Step 5/5')}
                lbl, desc, sl = labels.get(step, ('📡 CONSOL','Monitoring.',''))
                d2 = dict(data); d2['price'] = sp
                send(wh, embed_signal(cfg, d2, lbl, desc, sl, enter_now=(step==0)))
                if step == 0:
                    trade_open(cfg, data['signal'], sp, data['probability'], cfg['rr'])
                    state = {'active_signal':None,'signal_time':None,'signal_price':None,'countdown_step':0,'entry_mode':None}
        else:
            state = {'active_signal':None,'signal_time':None,'signal_price':None,'countdown_step':0,'entry_mode':None}
            send(wh, embed_monitoring(cfg, data))
    else:
        if state.get('entry_mode') == 'TREND':
            state = {'active_signal':None,'signal_time':None,'signal_price':None,'countdown_step':0,'entry_mode':None}
        send(wh, embed_monitoring(cfg, data))

    save_json(cfg['state_file'], state)
    save_pulse_log(cfg, data)

# ── DISCORD BOT STATUS UPDATE ─────────────────────────────────────────────────
def update_bot_status():
    """Post current active strategies to a status embed in #alerts."""
    token = os.environ.get('DISCORD_BOT_TOKEN', '')
    channel_id = '1472714063690862633'  # #alerts
    status_lines = []
    for key, cfg in STRATEGIES.items():
        log = load_json(cfg['pulse_log'], [])
        last = log[-1] if log else {}
        sig  = last.get('signal','—'); mode = last.get('mode','—'); prob = last.get('probability','—')
        tlog = load_json(cfg['trade_log'], [])
        closed = [t for t in tlog if t.get('result') in ('WIN','LOSS')]
        wins   = sum(1 for t in closed if t['result']=='WIN')
        net    = sum(t.get('pnl_usd',0) for t in closed)
        wr     = f"{wins/len(closed)*100:.0f}%" if closed else '—'
        open_t = load_json(cfg['trade_state'],{}).get('open')
        open_str = f"⚡ {open_t['signal']} OPEN" if open_t else '—'
        status_lines.append(f"{cfg['emoji']} **{cfg['name']}** — {sig} | {mode} | {prob}% | Trades:{len(closed)} WR:{wr} Net:${net:+.0f} | {open_str}")

    try:
        requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json={"content": "**🧿 AURA-V STRATEGY STATUS**\n" + "\n".join(status_lines)},
            timeout=10
        )
    except Exception as e:
        print(f"Status update error: {e}")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("Aura-V Multi-Strategy Relay starting...")
    df = fetch_raw()
    print(f"Data loaded: {len(df)} bars | Price: ${round(df['Close'].iloc[-1],2)}")

    for key in STRATEGIES:
        try:
            run_strategy(key, df)
        except Exception as e:
            print(f"[{key}] ERROR: {e}")

    # Post strategy status summary every pulse
    try:
        update_bot_status()
    except Exception as e:
        print(f"Status update error: {e}")

    print("\nAll strategies processed.")

if __name__ == "__main__":
    main()
