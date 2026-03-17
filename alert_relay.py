#!/usr/bin/env python3
"""
Aura-V 2.0 Pulse Relay - CLEAN FORMAT
Runs every 5 minutes via GitHub Actions
"""
import os
import json
import requests
import yfinance as yf
from datetime import datetime, timezone, timedelta

def fetch_gold_data():
    """Fetch XAUUSD data"""
    gold = yf.Ticker("GC=F")
    df = gold.history(period="2d", interval="1h")
    
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['Upper'] = df['SMA20'] + (df['STD20'] * 2.0)
    df['Lower'] = df['SMA20'] - (df['STD20'] * 2.0)
    
    latest = df.iloc[-1]
    
    return {
        'price': round(latest['Close'], 2),
        'upper': round(latest['Upper'], 2),
        'lower': round(latest['Lower'], 2),
        'sma': round(latest['SMA20'], 2)
    }

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
        # Distance to nearest band
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
    """Send CLEAN alert to Discord"""
    if not webhook_url:
        return
    
    now = datetime.now(timezone.utc)
    next_pulse = now + timedelta(minutes=5)
    next_time = next_pulse.strftime('%H:%M UTC')
    
    # Color based on signal
    color_map = {
        'BUY': 0x39d98a,
        'SELL': 0xff5d5d,
        'PREPARE': 0xf6c453,
        'WAIT': 0x888888
    }
    color = color_map.get(analysis['signal'], 0x888888)
    
    # Simple fields - NO LINKS, NO COMPLEX FORMATTING
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
            "value": f"```\n{analysis['probability']}%\n```",
            "inline": True
        },
        {
            "name": "STATUS",
            "value": f"```\n{analysis['status']}\n```",
            "inline": False
        },
        {
            "name": "NEXT PULSE",
            "value": f"```\n{next_time}\n```",
            "inline": True
        },
        {
            "name": "2.0 STD BANDS",
            "value": f"```\nUpper: ${data['upper']}\nLower: ${data['lower']}\n```",
            "inline": False
        }
    ]
    
    # Add GET READY warning if approaching
    if analysis['signal'] == 'PREPARE':
        fields.append({
            "name": "⚠️ ACTION REQUIRED",
            "value": "```\nGET READY - PRICE APPROACHING ENTRY ZONE\nSTANDBY FOR STAGE 1 TRIGGER\n```",
            "inline": False
        })
    
    embed = {
        "title": "🔱 AURA-V 2.0 PULSE",
        "color": color,
        "fields": fields,
        "timestamp": now.isoformat(),
        "footer": {"text": "5-Min Pulse | CST Localized"}
    }
    
    response = requests.post(
        webhook_url,
        json={"embeds": [embed]},
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Alert sent: {response.status_code}")

def save_log(data, analysis):
    """Save to pulse_log.json"""
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
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
    print("🚀 Pulse starting...")
    
    data = fetch_gold_data()
    analysis = calculate_analysis(data)
    
    print(f"Signal: {analysis['signal']} @ {analysis['probability']}%")
    
    webhook = os.environ.get('DISCORD_WEBHOOK_ALERTS')
    if webhook:
        send_discord_alert(webhook, data, analysis)
    
    save_log(data, analysis)
    
    print("✅ Done")

if __name__ == "__main__":
    main()
