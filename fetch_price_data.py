#!/usr/bin/env python3
"""
fetch_price_data.py
Fetches XAUUSD (Gold) OHLCV data via yfinance + Alpha Vantage fallback.
Writes price_data.json to repo root for the Market Kombat live chart.

Output format:
{
  "symbol": "XAUUSD",
  "updated": "2026-03-20 11:25 UTC",
  "bars_1m":  [ { "t": "2026-03-20 11:24:00", "o": 3025.10, "h": 3025.80, "l": 3024.50, "c": 3025.60, "v": 120 }, ... ],
  "bars_5m":  [ ... ],
  "bars_1h":  [ ... ],
  "current_price": 3025.60,
  "daily_high": 3031.20,
  "daily_low":  3019.40,
  "change_pct": 0.42,
  "bb_upper_5m": 3028.40,
  "bb_mid_5m":   3024.10,
  "bb_lower_5m": 3019.80,
  "sr_levels": [ { "type": "R", "price": 3031.20 }, { "type": "S", "price": 3019.40 } ]
}
"""

import json, math, os, sys
from datetime import datetime, timezone

try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False

def fetch_yfinance():
    if not YF_OK:
        return None
    try:
        ticker = yf.Ticker("GC=F")  # Gold futures (closest to XAUUSD)
        # 1-min bars last 1 day
        df_1m = ticker.history(period="1d", interval="1m")
        # 5-min bars last 5 days
        df_5m = ticker.history(period="5d", interval="5m")
        # 1-hour bars last 30 days
        df_1h = ticker.history(period="30d", interval="1h")
        if df_1m.empty and df_5m.empty:
            return None
        return df_1m, df_5m, df_1h
    except Exception as e:
        print(f"yfinance error: {e}", file=sys.stderr)
        return None

def fetch_alpha_vantage():
    api_key = os.environ.get("ALPHA_VANTAGE_KEY", "")
    if not api_key:
        return None
    try:
        import requests
        # Compact intraday 5-min
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=XAUUSD&interval=5min&outputsize=compact&apikey={api_key}"
        r = requests.get(url, timeout=15)
        data = r.json()
        ts = data.get("Time Series (5min)", {})
        if not ts:
            return None
        return ts  # dict of timestamp -> OHLCV
    except Exception as e:
        print(f"Alpha Vantage error: {e}", file=sys.stderr)
        return None

def df_to_bars(df):
    bars = []
    for ts, row in df.iterrows():
        t_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        bars.append({
            "t": t_str,
            "o": round(float(row["Open"]),  2),
            "h": round(float(row["High"]),  2),
            "l": round(float(row["Low"]),   2),
            "c": round(float(row["Close"]), 2),
            "v": int(row.get("Volume", 0))
        })
    return bars

def av_to_bars(ts_dict):
    bars = []
    for t, v in sorted(ts_dict.items()):
        bars.append({
            "t": t,
            "o": round(float(v["1. open"]),  2),
            "h": round(float(v["2. high"]),  2),
            "l": round(float(v["3. low"]),   2),
            "c": round(float(v["4. close"]), 2),
            "v": int(float(v["5. volume"]))
        })
    return bars

def calc_bb(bars, period=20, mult=2.0):
    if len(bars) < period:
        return None, None, None
    closes = [b["c"] for b in bars]
    sl = closes[-period:]
    avg = sum(sl)/period
    std = math.sqrt(sum((x-avg)**2 for x in sl)/period)
    return round(avg+mult*std,2), round(avg,2), round(avg-mult*std,2)

def find_sr(bars, pivot_window=3, max_levels=6):
    levels = []
    closes = [b["c"] for b in bars]
    n = len(closes)
    for i in range(pivot_window, n-pivot_window):
        window = closes[i-pivot_window:i+pivot_window+1]
        if closes[i] == max(window):
            levels.append({"type":"R","price":round(closes[i],2)})
        if closes[i] == min(window):
            levels.append({"type":"S","price":round(closes[i],2)})
    # Deduplicate close levels (within 0.5)
    unique = []
    for l in levels[-max_levels*3:]:
        if not any(abs(l["price"]-u["price"])<0.5 for u in unique):
            unique.append(l)
    return unique[-max_levels:]

def build_output(bars_1m, bars_5m, bars_1h):
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    current = bars_5m[-1]["c"] if bars_5m else (bars_1m[-1]["c"] if bars_1m else 0)
    prev_close = bars_1h[-2]["c"] if len(bars_1h) >= 2 else current
    change_pct = round((current - prev_close) / prev_close * 100, 3) if prev_close else 0
    daily_highs = [b["h"] for b in bars_1m] if bars_1m else [b["h"] for b in bars_5m]
    daily_lows  = [b["l"] for b in bars_1m] if bars_1m else [b["l"] for b in bars_5m]
    bb_upper, bb_mid, bb_lower = calc_bb(bars_5m)
    sr_levels = find_sr(bars_5m)

    return {
        "symbol":        "XAUUSD",
        "updated":       now_utc,
        "current_price": current,
        "daily_high":    round(max(daily_highs),2) if daily_highs else current,
        "daily_low":     round(min(daily_lows),2)  if daily_lows  else current,
        "change_pct":    change_pct,
        "bb_upper_5m":   bb_upper,
        "bb_mid_5m":     bb_mid,
        "bb_lower_5m":   bb_lower,
        "sr_levels":     sr_levels,
        "bars_1m":       bars_1m[-120:],   # last 2h of 1-min bars
        "bars_5m":       bars_5m[-288:],   # last 24h of 5-min bars
        "bars_1h":       bars_1h[-168:],   # last 7 days of hourly bars
    }

# ── Main ──────────────────────────────────────────────────────────
print("Fetching XAUUSD price data...")
result = fetch_yfinance()

if result:
    df_1m, df_5m, df_1h = result
    bars_1m = df_to_bars(df_1m) if not df_1m.empty else []
    bars_5m = df_to_bars(df_5m) if not df_5m.empty else []
    bars_1h = df_to_bars(df_1h) if not df_1h.empty else []
    print(f"yfinance: {len(bars_1m)} 1m bars, {len(bars_5m)} 5m bars, {len(bars_1h)} 1h bars")
else:
    print("yfinance failed, trying Alpha Vantage...")
    av = fetch_alpha_vantage()
    if av:
        bars_5m = av_to_bars(av)
        bars_1m = []
        bars_1h = []
        print(f"Alpha Vantage: {len(bars_5m)} 5m bars")
    else:
        print("Both sources failed — writing empty file")
        bars_1m, bars_5m, bars_1h = [], [], []

output = build_output(bars_1m, bars_5m, bars_1h)
with open("price_data.json", "w") as f:
    json.dump(output, f)

print(f"Wrote price_data.json — price: ${output['current_price']} | updated: {output['updated']}")
print(f"BB: {output['bb_lower_5m']} / {output['bb_mid_5m']} / {output['bb_upper_5m']}")
print(f"S/R levels: {output['sr_levels']}")
