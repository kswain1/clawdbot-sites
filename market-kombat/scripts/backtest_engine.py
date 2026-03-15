import sys
import argparse
import pandas as pd
import numpy as np
import yfinance as yf

def calculate_ema(prices, period):
    return prices.ewm(span=period, adjust=False).mean()

def run_backtest(strategy, std, rr, days):
    print(f"🚀 [SKILL: BACKTESTER] Initializing {strategy} | STD: {std} | RR: {rr} | {days} Days...")
    
    # 1. Fetch Data
    gold = yf.Ticker("GC=F")
    period = "1mo" if days <= 30 else "3mo"
    df = gold.history(period=period, interval="1h")
    
    if df.empty:
        print("❌ Data fetch failed.")
        return

    # 2. Indicators
    df['SMA20'] = df['Close'].rolling(args.ma_period).mean()
    df['STD20'] = df['Close'].rolling(args.ma_period).std()
    upper = df['SMA20'] + (df['STD20'] * std)
    lower = df['SMA20'] - (df['STD20'] * std)
    
    # 3. Simulation
    trades = []
    daily_count = {}
    
    for i in range(args.ma_period, len(df)):
        date_str = df.index[i].strftime('%Y-%m-%d')
        if daily_count.get(date_str, 0) >= 4: continue

        entry_type = None
        # Mean Reversion Logic
        if df['Close'].iloc[i] > upper.iloc[i]:
            entry_type = "SELL"
            sl_dist = max(abs(df['High'].iloc[i-4:i].max() - df['Close'].iloc[i]), 5.0)
            sl, tp = df['Close'].iloc[i] + sl_dist, df['Close'].iloc[i] - (sl_dist * rr)
        elif df['Close'].iloc[i] < lower.iloc[i]:
            entry_type = "BUY"
            sl_dist = max(abs(df['Close'].iloc[i] - df['Low'].iloc[i-4:i].min()), 5.0)
            sl, tp = df['Close'].iloc[i] - sl_dist, df['Close'].iloc[i] + (sl_dist * rr)

        if entry_type:
            for j in range(i+1, min(i+72, len(df))):
                if entry_type == "SELL":
                    if df['Low'].iloc[j] <= tp: trades.append(abs(df['Close'].iloc[i]-tp)*10); daily_count[date_str]=daily_count.get(date_str,0)+1; break
                    if df['High'].iloc[j] >= sl: trades.append(-abs(df['Close'].iloc[i]-sl)*10); daily_count[date_str]=daily_count.get(date_str,0)+1; break
                else:
                    if df['High'].iloc[j] >= tp: trades.append(abs(tp-df['Close'].iloc[i])*10); daily_count[date_str]=daily_count.get(date_str,0)+1; break
                    if df['Low'].iloc[j] <= sl: trades.append(-abs(sl-df['Close'].iloc[i])*10); daily_count[date_str]=daily_count.get(date_str,0)+1; break
            i += 24

    # 4. Results
    win_rate = (len([t for t in trades if t > 0]) / len(trades) * 100) if trades else 0
    print(f"\n🔱 BACKTEST COMPLETE")
    print(f"---")
    print(f"Total Trades: {len(trades)}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Net PnL: ${sum(trades):.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="Aura-V")
    parser.add_argument("--std", type=float, default=2.0)
    parser.add_argument("--rr", type=float, default=1.0)
    parser.add_argument("--ma_period", type=int, default=20)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    run_backtest(args.strategy, args.std, args.rr, args.days)
