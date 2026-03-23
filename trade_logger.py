#!/usr/bin/env python3
"""
trade_logger.py — Aura-V Auto Paper Trade Tracker
────────────────────────────────────────────────────
Runs after every pulse. When ENTER NOW fires:
  → Opens a trade at current price
  → Monitors subsequent pulses for target / stop hit
  → Closes trade, logs result, posts result to #trade-log

trade_log.json schema per entry:
{
  "id":          "T001",
  "opened_at":   "2026-03-22 18:03 CST",
  "closed_at":   "2026-03-22 18:47 CST",
  "hold_min":    44,
  "signal":      "BUY",
  "mode":        "TREND",
  "entry":       2340.50,
  "target":      2396.50,   # entry + rr * risk
  "stop":        2320.50,   # entry - risk
  "risk_pts":    20,
  "rr":          2.8,
  "exit":        2396.50,
  "exit_reason": "TARGET",  # TARGET | STOP | TIMEOUT | MANUAL
  "pnl_pts":     +56.0,
  "pnl_usd":     +560.0,    # pnl_pts * contract_size
  "result":      "WIN",
  "probability": 78.4,
  "contract":    10.0
}
"""
import os, json, math, requests
from datetime import datetime, timezone, timedelta

CST         = timedelta(hours=-6)
RISK_PTS    = 20
RR          = 2.8
CONTRACT    = 10.0          # $/pt per contract
DAILY_CAP   = 400.0
TIMEOUT_MIN = 120           # auto-close after 2 hours if neither target nor stop hit

TRADE_LOG   = 'trade_log.json'
STATE_FILE  = 'trade_state.json'

def now_utc():  return datetime.now(timezone.utc)
def cst(dt):    return dt + CST
def ts():       return cst(now_utc()).strftime('%Y-%m-%d %H:%M CST')

WEBHOOK_TRADE = os.environ.get('DISCORD_WEBHOOK_TRADE_LOG',
                os.environ.get('DISCORD_WEBHOOK_ALERTS',
                'https://discord.com/api/webhooks/1485448651362013194/2goZ_3_asEnwJQeraqB2nLQXRCrtkyYKg7lhNC7K-qHDdXHyLyQs-13eIuNpCO1ZvYx3'))

# ── I/O helpers ──────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path) as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=2)

def load_log():   return load_json(TRADE_LOG, [])
def load_state(): return load_json(STATE_FILE, {'open_trade': None, 'next_id': 1, 'daily': {}})

def next_trade_id(state):
    n = state.get('next_id', 1)
    state['next_id'] = n + 1
    return f"T{n:03d}"

# ── Discord post ──────────────────────────────────────────────────────────────
def post_discord(embed):
    if not WEBHOOK_TRADE: return
    try:
        requests.post(WEBHOOK_TRADE, json={'embeds': [embed]}, timeout=10)
    except Exception as e:
        print(f"Discord error: {e}")

def embed_open(trade):
    color  = 0x39d98a if trade['signal'] == 'BUY' else 0xff5d5d
    arrow  = '▲' if trade['signal'] == 'BUY' else '▼'
    return {
        "title": f"📋 TRADE OPENED — {arrow} {trade['signal']} #{trade['id']}",
        "color": color,
        "fields": [
            {"name": "MODE",    "value": f"```\n{trade['mode']}\n```",        "inline": True},
            {"name": "ENTRY",   "value": f"```\n${trade['entry']}\n```",      "inline": True},
            {"name": "PROB",    "value": f"```\n{trade['probability']}%\n```","inline": True},
            {"name": "TARGET",  "value": f"```\n${trade['target']} (+{trade['risk_pts']*trade['rr']:.0f} pts)\n```", "inline": True},
            {"name": "STOP",    "value": f"```\n${trade['stop']} (-{trade['risk_pts']} pts)\n```",  "inline": True},
            {"name": "R:R",     "value": f"```\n1:{trade['rr']}\n```",        "inline": True},
        ],
        "timestamp": now_utc().isoformat(),
        "footer": {"text": f"Aura-V Paper Tracker | {trade['opened_at']}"}
    }

def embed_close(trade):
    win    = trade['result'] == 'WIN'
    color  = 0x39d98a if win else 0xff5d5d
    icon   = '✅' if win else '❌'
    pnl    = trade['pnl_usd']
    return {
        "title": f"{icon} TRADE CLOSED — {trade['signal']} #{trade['id']} — {'WIN' if win else 'LOSS'}",
        "color": color,
        "fields": [
            {"name": "EXIT REASON", "value": f"```\n{trade['exit_reason']}\n```",   "inline": True},
            {"name": "EXIT PRICE",  "value": f"```\n${trade['exit']}\n```",          "inline": True},
            {"name": "HOLD TIME",   "value": f"```\n{trade['hold_min']} min\n```",   "inline": True},
            {"name": "P&L (pts)",   "value": f"```\n{trade['pnl_pts']:+.1f} pts\n```", "inline": True},
            {"name": "P&L (USD)",   "value": f"```\n${pnl:+.2f}\n```",              "inline": True},
            {"name": "ENTRY→EXIT",  "value": f"```\n${trade['entry']} → ${trade['exit']}\n```", "inline": True},
        ],
        "timestamp": now_utc().isoformat(),
        "footer": {"text": f"Aura-V Paper Tracker | Opened {trade['opened_at']}"}
    }

def embed_daily_summary(date_str, wins, losses, pnl_usd):
    color = 0x39d98a if pnl_usd >= 0 else 0xff5d5d
    wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    return {
        "title": f"📊 DAILY SUMMARY — {date_str}",
        "color": color,
        "fields": [
            {"name": "TRADES",  "value": f"```\n{wins+losses} total\n```",   "inline": True},
            {"name": "WIN RATE","value": f"```\n{wr:.0f}%\n```",             "inline": True},
            {"name": "NET P&L", "value": f"```\n${pnl_usd:+.2f}\n```",      "inline": True},
            {"name": "WINS",    "value": f"```\n{wins}\n```",                "inline": True},
            {"name": "LOSSES",  "value": f"```\n{losses}\n```",              "inline": True},
            {"name": "DAILY CAP","value": f"```\n${DAILY_CAP:.0f}\n```",    "inline": True},
        ],
        "timestamp": now_utc().isoformat(),
        "footer": {"text": "Aura-V Paper Tracker — Daily Close"}
    }

# ── Core logic ────────────────────────────────────────────────────────────────
def open_trade(state, signal, mode, price, prob):
    """Called when ENTER NOW fires."""
    trade_id = next_trade_id(state)
    if signal == 'BUY':
        target = round(price + RISK_PTS * RR, 2)
        stop   = round(price - RISK_PTS, 2)
    else:
        target = round(price - RISK_PTS * RR, 2)
        stop   = round(price + RISK_PTS, 2)

    trade = {
        'id':          trade_id,
        'opened_at':   ts(),
        'opened_utc':  now_utc().isoformat(),
        'closed_at':   None,
        'hold_min':    None,
        'signal':      signal,
        'mode':        mode,
        'entry':       price,
        'target':      target,
        'stop':        stop,
        'risk_pts':    RISK_PTS,
        'rr':          RR,
        'exit':        None,
        'exit_reason': None,
        'pnl_pts':     None,
        'pnl_usd':     None,
        'result':      'OPEN',
        'probability': prob,
        'contract':    CONTRACT,
    }
    state['open_trade'] = trade
    print(f"TRADE OPENED: {trade_id} {signal} @ ${price} | target=${target} stop=${stop}")
    post_discord(embed_open(trade))
    return trade

def check_close(state, current_price):
    """Called every pulse when a trade is open. Returns closed trade or None."""
    trade = state.get('open_trade')
    if not trade or trade['result'] != 'OPEN':
        return None

    signal   = trade['signal']
    target   = trade['target']
    stop     = trade['stop']
    entry    = trade['entry']
    opened   = datetime.fromisoformat(trade['opened_utc'])
    hold_min = int((now_utc() - opened).total_seconds() / 60)

    hit_target = (signal == 'BUY'  and current_price >= target) or \
                 (signal == 'SELL' and current_price <= target)
    hit_stop   = (signal == 'BUY'  and current_price <= stop)   or \
                 (signal == 'SELL' and current_price >= stop)
    timed_out  = hold_min >= TIMEOUT_MIN

    if not (hit_target or hit_stop or timed_out):
        print(f"TRADE OPEN: #{trade['id']} {signal} @ ${entry} | current=${current_price} | {hold_min}min elapsed")
        return None

    # Determine exit
    if hit_target:
        exit_price  = target
        exit_reason = 'TARGET'
        result      = 'WIN'
    elif hit_stop:
        exit_price  = stop
        exit_reason = 'STOP'
        result      = 'LOSS'
    else:
        exit_price  = current_price
        exit_reason = 'TIMEOUT'
        pnl_pts_raw = (current_price - entry) if signal == 'BUY' else (entry - current_price)
        result      = 'WIN' if pnl_pts_raw > 0 else 'LOSS'

    pnl_pts = (exit_price - entry) if signal == 'BUY' else (entry - exit_price)
    pnl_usd = round(pnl_pts * CONTRACT, 2)

    trade.update({
        'closed_at':   ts(),
        'hold_min':    hold_min,
        'exit':        exit_price,
        'exit_reason': exit_reason,
        'pnl_pts':     round(pnl_pts, 2),
        'pnl_usd':     pnl_usd,
        'result':      result,
    })

    state['open_trade'] = None

    # Daily tracking
    today = cst(now_utc()).strftime('%Y-%m-%d')
    d = state.setdefault('daily', {}).setdefault(today, {'wins': 0, 'losses': 0, 'pnl': 0.0})
    if result == 'WIN': d['wins'] += 1
    else:               d['losses'] += 1
    d['pnl'] = round(d['pnl'] + pnl_usd, 2)

    print(f"TRADE CLOSED: #{trade['id']} {result} | exit={exit_price} reason={exit_reason} pnl=${pnl_usd:+.2f} | {hold_min}min")
    post_discord(embed_close(trade))

    # Daily cap check
    if abs(d['pnl']) >= DAILY_CAP and d['pnl'] < 0:
        print(f"⛔ DAILY LOSS CAP HIT: ${d['pnl']:.2f} — no more trades today")
        post_discord({
            "title": "⛔ DAILY LOSS CAP HIT — Trading Halted",
            "color": 0xff5d5d,
            "description": f"Daily loss reached **${d['pnl']:.2f}** (cap: -${DAILY_CAP:.0f}). No new trades for remainder of session.",
            "timestamp": now_utc().isoformat(),
            "footer": {"text": "Aura-V Risk Manager"}
        })

    return trade

def daily_cap_breached(state):
    """Returns True if today's loss has hit or exceeded DAILY_CAP."""
    today = cst(now_utc()).strftime('%Y-%m-%d')
    d = state.get('daily', {}).get(today, {})
    pnl = d.get('pnl', 0.0)
    return pnl <= -DAILY_CAP

# ── Main entry (called from alert_relay.py) ───────────────────────────────────
def process_pulse(signal, mode, price, prob, enter_now=False):
    """
    Call this from alert_relay.py on every pulse.
    enter_now=True  → ENTER NOW fired (step 0 of countdown)
    """
    state = load_state()
    log   = load_log()
    changed = False

    # 1. Check if open trade should close
    if state.get('open_trade'):
        closed = check_close(state, price)
        if closed:
            log.append(closed)
            changed = True

    # 2. Open new trade if ENTER NOW and no daily cap breach and no open trade
    if enter_now and not state.get('open_trade') and not daily_cap_breached(state):
        if signal in ('BUY', 'SELL') and prob > 60:
            open_trade(state, signal, mode, price, prob)
            changed = True
        else:
            print(f"ENTER NOW skipped — signal={signal} prob={prob}%")

    if changed or enter_now:
        save_json(STATE_FILE, state)
        save_json(TRADE_LOG, log[-200:])  # keep last 200 trades

    return state

def get_stats():
    """Return summary stats for dashboard / site."""
    log = load_log()
    if not log:
        return {'trades': 0, 'wins': 0, 'losses': 0, 'wr': 0, 'net_usd': 0, 'streak': 0}

    closed = [t for t in log if t.get('result') in ('WIN', 'LOSS')]
    wins   = sum(1 for t in closed if t['result'] == 'WIN')
    losses = len(closed) - wins
    net    = sum(t.get('pnl_usd', 0) for t in closed)
    wr     = round(wins / len(closed) * 100, 1) if closed else 0

    # current streak
    streak = 0
    if closed:
        last = closed[-1]['result']
        for t in reversed(closed):
            if t['result'] == last: streak += 1
            else: break
        streak = streak if last == 'WIN' else -streak

    return {
        'trades': len(closed), 'wins': wins, 'losses': losses,
        'wr': wr, 'net_usd': round(net, 2), 'streak': streak,
        'open': bool(load_state().get('open_trade'))
    }

if __name__ == '__main__':
    # Test run
    print("Trade Logger — Stats:")
    print(json.dumps(get_stats(), indent=2))
