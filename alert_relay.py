#!/usr/bin/env python3
"""
Aura-V 2.0 Pulse Relay - CLEAN FORMAT with CST times + Alpha Vantage fallback
Runs every 5 minutes via GitHub Actions
"""
import os
import json
import requests
import yfinance as yf
from datetime import datetime, timezone, timedelta

CST_OFFSET = timedelta(hours=-6)  # UTC-6 for CST

def utc_to_cst(dt_utc):
    return dt_utc + CST_OFFSET

def get_prob_bar(probability):
    """Visual probability bar"""
    filled = int(probability / 10)
    return '█' * filled + '░' * (10 - filled)

def fetch_gold_yfinance():
    """Fetch XAUUSD data via yfinance (primary)"""
    gold = yf.Ticker("GC=F")
    df = gold.history(period="2d", interval="1h")
    if df.empty:
        return None

    df['SMA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['Upper'] = df['SMA20'] + (df['STD20'] * 2.0)
    df['Lower'] = df['SMA20'] - (df['STD20'] * 2.0)

    latest = df.iloc[-1]
    return {
        'price': round(latest['Close'], 2),
        'upper': round(latest['Upper'], 2),
        'lower': round(latest['Lower'], 2),
        'sma': round(latest['SMA20'], 2),
        'source': 'yfinance'
    }

def fetch_gold_alpha_vantage():
    """Fetch XAUUSD via Alpha Vantage (backup)"""
    api_key = os.environ.get('ALPHA_VANTAGE_KEY', 'demo')
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=XAU&to_symbol=USD&interval=60min&apikey={api_key}&outputsize=compact"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        series = data.get("Time Series FX (60min)", {})
        if not series:
            return None
        prices = [float(v['4. close']) for v in list(series.values())[:20]]
        prices.reverse()
        import statistics
        sma = statistics.mean(prices)
        std = statistics.stdev(prices)
        price = prices[-1]
        return {
            'price': round(price, 2),
            'upper': round(sma + std * 2.0, 2),
            'lower': round(sma - std * 2.0, 2),
            'sma': round(sma, 2),
            'source': 'alpha_vantage'
        }
    except Exception as e:
        print(f"Alpha Vantage error: {e}")
        return None

def fetch_gold_data():
    """Try yfinance first, fallback to Alpha Vantage"""
    data = fetch_gold_yfinance()
    if data:
        return data
    print("yfinance failed, trying Alpha Vantage backup...")
    data = fetch_gold_alpha_vantage()
    if data:
        return data
    raise Exception("All data sources failed")

def calculate_analysis(data):
    """Aura-V 2.0 Analysis"""
    price = data['price']
    upper = data['upper']
    lower = data['lower']

    if price > upper:
        prob = min(95, 75 + (price - upper) * 2)
        signal = "SELL"
        status = "STAGE 1 TRIGGER"
    elif price < lower:
        prob = min(95, 75 + (lower - price) * 2)
        signal = "BUY"
        status = "STAGE 1 TRIGGER"
    else:
        dist_to_upper = abs(price - upper)
        dist_to_lower = abs(price - lower)
        nearest = min(dist_to_upper, dist_to_lower)

        if nearest < 5:
            prob = 65
            signal = "PREPARE"
            status = "APPROACHING ZONE"
        else:
            prob = max(10, 50 - nearest * 0.3)
            signal = "WAIT"
            status = "CONSOLIDATION"

    return {
        'probability': round(prob, 1),
        'signal': signal,
        'status': status
    }

def send_discord_alert(webhook_url, data, analysis):
    """Send clean alert to Discord"""
    if not webhook_url:
        return

    now_utc = datetime.now(timezone.utc)
    now_cst = utc_to_cst(now_utc)
    next_cst = utc_to_cst(now_utc + timedelta(minutes=5))

    color_map = {
        'BUY': 0x39d98a,
        'SELL': 0xff5d5d,
        'PREPARE': 0xf6c453,
        'WAIT': 0x888888
    }
    color = color_map.get(analysis['signal'], 0x888888)

    fields = [
        {
            "name": "SIGNAL",
            "value": f"```\n{analysis['signal']}\n```",
            "inline": True
        },
        {
            "name": "PRICE",
            "value": f"```\n${data['price']}\n```",
            "inline": True
        },
        {
            "name": "PROBABILITY",
            "value": f"```\n{analysis['probability']}%\n{get_prob_bar(analysis['probability'])}\n```",
            "inline": True
        },
        {
            "name": "STATUS",
            "value": f"```\n{analysis['status']}\n```",
            "inline": False
        },
        {
            "name": "TIME (CST)",
            "value": f"```\n{now_cst.strftime('%H:%M CST')}\n```",
            "inline": True
        },
        {
            "name": "NEXT PULSE (CST)",
            "value": f"```\n{next_cst.strftime('%H:%M CST')}\n```",
            "inline": True
        },
        {
            "name": "2.0 STD BANDS",
            "value": f"```\nUpper: ${data['upper']}\nLower: ${data['lower']}\n```",
            "inline": False
        }
    ]

    if analysis['signal'] == 'PREPARE':
        fields.append({
            "name": "ACTION REQUIRED",
            "value": "```\nGET READY - PRICE APPROACHING ENTRY ZONE\nSTANDBY FOR STAGE 1 TRIGGER\n```",
            "inline": False
        })

    embed = {
        "title": "AURA-V 2.0 PULSE",
        "color": color,
        "fields": fields,
        "timestamp": now_utc.isoformat(),
        "footer": {"text": f"5-Min Pulse | Source: {data.get('source', 'unknown')}"}
    }

    response = requests.post(
        webhook_url,
        json={"embeds": [embed]},
        headers={"Content-Type": "application/json"}
    )
    print(f"Alert sent: {response.status_code}")

def save_log(data, analysis):
    """Save to pulse_log.json"""
    now_utc = datetime.now(timezone.utc)
    now_cst = utc_to_cst(now_utc)
    entry = {
        "timestamp": now_cst.strftime('%Y-%m-%d %H:%M CST'),
        "price": data['price'],
        "probability": analysis['probability'],
        "signal": analysis['signal'],
        "status": analysis['status']
    }

    try:
        with open('pulse_log.json', 'r') as f:
            logs = json.load(f)
    except:
        logs = []

    logs.append(entry)
    logs = logs[-100:]

    with open('pulse_log.json', 'w') as f:
        json.dump(logs, f, indent=2)

def main():
    print("Pulse starting...")
    data = fetch_gold_data()
    analysis = calculate_analysis(data)
    print(f"Signal: {analysis['signal']} @ {analysis['probability']}% | Source: {data['source']}")

    webhook = os.environ.get('DISCORD_WEBHOOK_ALERTS')
    if webhook:
        send_discord_alert(webhook, data, analysis)

    save_log(data, analysis)
    print("Done")

if __name__ == "__main__":
    main()
