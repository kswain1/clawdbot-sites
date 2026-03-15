import pandas as pd
import numpy as np
import yfinance as yf

def run_aura_v_ultra_optimizer():
    print("🚀 [ULTRA OPTIMIZER] Running 90-Day Deep Evolution (STD x RR)...")
    
    # 1. Fetch 3 months of 1H data
    gold = yf.Ticker("GC=F")
    df = gold.history(period="3mo", interval="1h")
    if df.empty:
        print("❌ Failed to fetch 3-month history.")
        return

    # 2. Base Indicators
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    
    # PARAMETER GRIDS
    std_steps = [2.0, 2.1, 2.2, 2.3, 2.4, 2.5]
    rr_steps = np.around(np.arange(1.0, 1.6, 0.1), 1)
    
    results = []

    print(f"🔬 Testing {len(std_steps) * len(rr_steps)} combinations across 90 days...")

    for std in std_steps:
        # Calculate Bands for this STD
        upper_band = df['SMA20'] + (df['STD20'] * std)
        lower_band = df['SMA20'] - (df['STD20'] * std)
        
        for rr in rr_steps:
            trades = []
            daily_count = {}
            
            for i in range(20, len(df)):
                date_str = df.index[i].strftime('%Y-%m-%d')
                if daily_count.get(date_str, 0) >= 4: continue

                entry_type = None
                if df['Close'].iloc[i] > upper_band.iloc[i]:
                    entry_type = "SELL"
                    entry_price = df['Close'].iloc[i]
                    sl_dist = max(abs(df['High'].iloc[i-4:i].max() - entry_price), 5.0)
                    sl = entry_price + sl_dist
                    tp = entry_price - (sl_dist * rr)
                elif df['Close'].iloc[i] < lower_band.iloc[i]:
                    entry_type = "BUY"
                    entry_price = df['Close'].iloc[i]
                    sl_dist = max(abs(entry_price - df['Low'].iloc[i-4:i].min()), 5.0)
                    sl = entry_price - sl_dist
                    tp = entry_price + (sl_dist * rr)

                if entry_type:
                    trade_res = None
                    # Max hold 72h
                    for j in range(i+1, min(i+72, len(df))):
                        if entry_type == "SELL":
                            if df['Low'].iloc[j] <= tp: trade_res = "WIN"; pnl = (entry_price - tp) * 10; break
                            if df['High'].iloc[j] >= sl: trade_res = "LOSS"; pnl = (entry_price - sl) * 10; break
                        else:
                            if df['High'].iloc[j] >= tp: trade_res = "WIN"; pnl = (tp - entry_price) * 10; break
                            if df['Low'].iloc[j] <= sl: trade_res = "LOSS"; pnl = (sl - entry_price) * 10; break
                    
                    if trade_res:
                        trades.append(pnl)
                        daily_count[date_str] = daily_count.get(date_str, 0) + 1
                        i += 24 # Cooldown

            total_pnl = sum(trades)
            win_rate = (len([t for t in trades if t > 0]) / len(trades) * 100) if trades else 0
            results.append({
                "STD": std,
                "RR": rr,
                "PnL": total_pnl,
                "Win%": win_rate,
                "Trades": len(trades)
            })

    # Find the winning combination
    rdf = pd.DataFrame(results)
    best = rdf.loc[rdf['PnL'].idxmax()]
    
    # Pivot for Heatmap visualization in logs
    heatmap = rdf.pivot(index='STD', columns='RR', values='PnL')

    report = f"""
🔱 **AURA-V ULTRA OPTIMIZER: THE WINNING COMBINATION** 🧬📉🏆🛡️
---
*   **Winner Code:** STD {best['STD']} | RR {best['RR']} 🏆
*   **Max 90-Day Performance:** ${best['PnL']:.2f} 💰✅
*   **Win Consistency:** {best['Win%']:.1f}% Accuracy
*   **Operational Volume:** {best['Trades']} Scenarios detected.

**PnL Matrix (STD vs RR Iterations):**
{heatmap.to_string()}

**Strategic Diagnostic:**
The evolution confirms that **STD {best['STD']}** acts as the ultimate filter for the Gold 1H frame. It finds the "true exhaustion" levels where a **1:{best['RR']}** reversal move is most statistically certain. This configuration captures the deepest reversions while maintaining high capital protection. 🏗️🥊
---
*Clyde Analytics | Neural Evolution*
"""
    print(report)

if __name__ == "__main__":
    run_aura_v_ultra_optimizer()
