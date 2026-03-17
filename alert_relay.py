#!/usr/bin/env python3
"""
Aura-V 2.0 Multi-Channel Alert Relay
Runs via GitHub Actions every 15 minutes
"""
import os
import json
import requests
import yfinance as yf
from datetime import datetime, timezone

def fetch_gold_data():
    """Fetch XAUUSD 1h data for Aura-V analysis"""
    gold = yf.Ticker("GC=F")
    df = gold.history(period="2d", interval="1h")
    
    # Aura-V 2.0 Indicators
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['Upper'] = df['SMA20'] + (df['STD20'] * 2.0)
    df['Lower'] = df['SMA20'] - (df['STD20'] * 2.0)
    
    latest = df.iloc[-1]
    
    return {
        'price': round(latest['Close'], 2),
        'upper_band': round(latest['Upper'], 2),
        'lower_band': round(latest['Lower'], 2),
        'sma20': round(latest['SMA20'], 2),
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    }

def calculate_probability(data):
    """Aura-V 2.0 Probability Engine"""
    price = data['price']
    upper = data['upper_band']
    lower = data['lower_band']
    sma = data['sma20']
    
    # Distance from bands
    dist_upper = abs(price - upper)
    dist_lower = abs(price - lower)
    dist_mean = abs(price - sma)
    
    # Probability calculation
    if price > upper:
        prob = min(95, 75 + (price - upper) * 2)
        signal = "SELL"
    elif price < lower:
        prob = min(95, 75 + (lower - price) * 2)
        signal = "BUY"
    else:
        prob = max(10, 50 - dist_mean * 0.5)
        signal = "NEUTRAL"
    
    return {
        'probability': round(prob, 1),
        'signal': signal,
        'stage': 'STAGE 1 [800s]' if prob > 75 else 'MONITORING'
    }

def send_discord_alert(webhook_url, data, analysis):
    """Send formatted alert to Discord via Webhook"""
    if not webhook_url:
        print("No webhook URL provided, skipping Discord")
        return
    
    # Format probability bar
    filled = int(analysis['probability'] / 10)
    bar = '█' * filled + '░' * (10 - filled)
    
    embed = {
        "title": "🔱 Aura-V 2.0 Pulse",
        "description": f"**{analysis['signal']} Signal Detected**",
        "color": 0xf6c453 if analysis['signal'] == 'BUY' else 0xff5d5d if analysis['signal'] == 'SELL' else 0x888888,
        "fields": [
            {"name": "Price", "value": f"${data['price']}", "inline": True},
            {"name": "Probability", "value": f"{analysis['probability']}% {bar}", "inline": True},
            {"name": "Stage", "value": analysis['stage'], "inline": True},
            {"name": "Upper Band (2.0 STD)", "value": f"${data['upper_band']}", "inline": True},
            {"name": "Lower Band (2.0 STD)", "value": f"${data['lower_band']}", "inline": True},
            {"name": "Timestamp", "value": data['timestamp'], "inline": False}
        ],
        "footer": {"text": "Aura Intelligence | Institutional Command"}
    }
    
    payload = {"embeds": [embed]}
    
    response = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 204:
        print(f"✅ Alert sent successfully to {webhook_url[:50]}...")
    else:
        print(f"❌ Failed to send: {response.status_code}")

def save_pulse_log(data, analysis):
    """Save pulse data for dashboard sync"""
    log_entry = {
        "timestamp": data['timestamp'],
        "price": data['price'],
        "probability": analysis['probability'],
        "signal": analysis['signal'],
        "stage": analysis['stage']
    }
    
    # Append to pulse log
    log_file = "pulse_log.json"
    try:
        with open(log_file, 'r') as f:
            logs = json.load(f)
    except:
        logs = []
    
    logs.append(log_entry)
    
    # Keep only last 100 entries
    logs = logs[-100:]
    
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2)
    
    print(f"💾 Pulse logged: {log_entry}")

def main():
    print("🚀 Aura-V 2.0 Pulse Relay Starting...")
    
    # Fetch data
    data = fetch_gold_data()
    print(f"📊 Data fetched: ${data['price']}")
    
    # Analyze
    analysis = calculate_probability(data)
    print(f"🧠 Analysis: {analysis['signal']} @ {analysis['probability']}%")
    
    # Send to Discord Alerts (if high conviction)
    if analysis['probability'] > 50:
        alerts_webhook = os.environ.get('DISCORD_WEBHOOK_ALERTS')
        if alerts_webhook:
            send_discord_alert(alerts_webhook, data, analysis)
    
    # Always send to Inbox for logging
    inbox_webhook = os.environ.get('DISCORD_WEBHOOK_INBOX')
    if inbox_webhook:
        send_discord_alert(inbox_webhook, data, analysis)
    
    # Save to file
    save_pulse_log(data, analysis)
    
    print("✅ Pulse relay complete")

if __name__ == "__main__":
    main()
