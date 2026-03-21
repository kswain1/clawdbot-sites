#!/usr/bin/env python3
"""
backtest_eval_180.py — 180-day evaluation harness
4 regimes: Bull → Chop → Bear → Recovery
Metric: EV ratio (higher = better)
"""
import json, math, random, sys

RISK = 20.0; CONTRACT = 10.0; DAILY_CAP = 400.0
BARS_PER_DAY = 288; DAYS = 180; SEED = 42

def generate_prices_180():
    """
    180-day realistic XAUUSD-like price series with 4 regimes:
      Days   0– 44: Bull rally       (+0.030 drift/bar avg)
      Days  45– 89: Choppy/sideways  (+0.002 drift, high noise)
      Days  90–134: Bear leg         (-0.025 drift/bar avg)
      Days 135–179: Recovery         (+0.018 drift, moderate noise)
    """
    random.seed(SEED)
    prices = []
    p = 4800.0
    for d in range(DAYS):
        if d < 45:      drift, noise = 0.030, 2.2    # bull
        elif d < 90:    drift, noise = 0.002, 3.8    # chop
        elif d < 135:   drift, noise = -0.025, 2.8   # bear
        else:           drift, noise = 0.018, 2.5    # recovery
        for b in range(BARS_PER_DAY):
            p += drift + random.gauss(0, noise)
            prices.append(round(max(p, 3000.0), 2))
    return prices

def rolling_sma(data, n):
    out = [None]*len(data)
    for i in range(n-1, len(data)): out[i] = sum(data[i-n+1:i+1])/n
    return out

def rolling_std(data, n):
    out = [None]*len(data)
    for i in range(n-1, len(data)):
        sl = data[i-n+1:i+1]; m = sum(sl)/n
        out[i] = math.sqrt(sum((x-m)**2 for x in sl)/n)
    return out

def get_htf_bias(prices, bar, tf_bars):
    if bar < tf_bars * 4: return 'NEUTRAL'
    htf = []
    i = bar - tf_bars * 4
    while i + tf_bars <= bar: htf.append(prices[i+tf_bars-1]); i += tf_bars
    if len(htf) < 4: return 'NEUTRAL'
    sma_val = sum(htf[-4:])/4
    if htf[-1] > sma_val*1.001 and htf[-1] > htf[-2]: return 'BULL'
    if htf[-1] < sma_val*0.999 and htf[-1] < htf[-2]: return 'BEAR'
    return 'NEUTRAL'

def run_backtest(params, prices=None):
    random.seed(SEED)
    if prices is None: prices = generate_prices_180()
    N = len(prices)
    bp = params.get('bb_period',20); bs = params.get('bb_std',2.0)
    rr = params.get('rr',2.8); htf = params.get('htf_bars',48)
    mp = params.get('min_prob',0.25); eh = params.get('entry_hours',[8,9,18,19,20])

    bb_mid = rolling_sma(prices,bp); bb_s = rolling_std(prices,bp)
    bb_u = [bb_mid[i]+bs*bb_s[i] if bb_mid[i] else None for i in range(N)]
    bb_l = [bb_mid[i]-bs*bb_s[i] if bb_mid[i] else None for i in range(N)]

    equity = 10000.0; trades = []; daily_pnl = {}
    regime_trades = {'bull':[],'chop':[],'bear':[],'recovery':[]}

    for i in range(bp, N-10):
        if not bb_u[i]: continue
        hour = (i % BARS_PER_DAY)*5//60
        if hour not in eh: continue
        if prices[i] < bb_l[i]: d = 'BUY'
        elif prices[i] > bb_u[i]: d = 'SELL'
        else: continue
        bias = get_htf_bias(prices, i, htf)
        if bias!='NEUTRAL' and ((d=='BUY' and bias=='BEAR') or (d=='SELL' and bias=='BULL')): continue
        day = i//BARS_PER_DAY
        if daily_pnl.get(day,0) <= -DAILY_CAP: continue
        look = max(0,i-48); trend_up = prices[i] > prices[look]
        aligned = (d=='BUY' and trend_up) or (d=='SELL' and not trend_up)
        raw_prob = max(0.05, min(0.95, random.gauss(0.42 if aligned else 0.21, 0.08 if aligned else 0.06)))
        if raw_prob < mp: continue
        target = RISK*rr; win = random.random() < raw_prob
        pnl = (target if win else -RISK)*CONTRACT
        equity += pnl; daily_pnl[day] = daily_pnl.get(day,0)+pnl
        t = {'win':win,'pnl':pnl,'day':day}
        trades.append(t)
        if day < 45: regime_trades['bull'].append(t)
        elif day < 90: regime_trades['chop'].append(t)
        elif day < 135: regime_trades['bear'].append(t)
        else: regime_trades['recovery'].append(t)

    if not trades: return {'ev':-999,'net':0,'wr':0,'trades':0,'grade':'F','max_dd':100,'regimes':{}}
    wins=[t for t in trades if t['win']]; losses=[t for t in trades if not t['win']]
    wr=len(wins)/len(trades); net=equity-10000
    avg_w=sum(t['pnl'] for t in wins)/len(wins) if wins else 0
    avg_l=sum(t['pnl'] for t in losses)/len(losses) if losses else 0
    ev=(wr*avg_w+(1-wr)*avg_l)/abs(avg_l) if avg_l else 0
    eq=[10000.0]; [eq.append(eq[-1]+t['pnl']) for t in trades]
    peak=eq[0]; dd=0
    for e in eq: peak=max(peak,e); dd=max(dd,(peak-e)/peak*100)
    g='F' if ev<-0.2 else 'D' if ev<0 else 'C' if ev<0.15 else 'B' if ev<0.3 else 'B+' if ev<0.5 else 'A-' if ev<0.7 else 'A'

    # Per-regime stats
    def regime_stats(ts):
        if not ts: return {'wr':0,'net':0,'trades':0,'ev':0}
        w=[t for t in ts if t['win']]; l=[t for t in ts if not t['win']]
        rwr=len(w)/len(ts)
        aw=sum(t['pnl'] for t in w)/len(w) if w else 0
        al=sum(t['pnl'] for t in l)/len(l) if l else 0
        rev=(rwr*aw+(1-rwr)*al)/abs(al) if al else 0
        return {'wr':round(rwr*100,1),'net':round(sum(t['pnl'] for t in ts),2),'trades':len(ts),'ev':round(rev,3)}

    regimes = {k: regime_stats(v) for k,v in regime_trades.items()}
    return {'ev':round(ev,4),'net':round(net,2),'wr':round(wr*100,1),'trades':len(trades),'grade':g,'max_dd':round(dd,1),'regimes':regimes}

if __name__ == '__main__':
    params = json.loads(sys.argv[1]) if len(sys.argv)>1 else {}
    print(json.dumps(run_backtest(params), indent=2))
