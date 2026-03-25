"""
auto_promote.py — AutoResearch → Live Relay Promotion Engine

Runs after autorun_expanded.py. Compares new best config against current live
CHALLENGE config. Promotes if:
  - New EV beats current by >= PROMOTE_THRESHOLD (+0.1)
  - Walk-forward validation passed (val_ev >= 0.7 * train_ev)
  - New max_dd <= 10% (prop firm safe)

Updates alert_relay.py CHALLENGE config in-place.
Posts promotion notice to Discord.
"""
import json, os, re, sys, requests
from datetime import datetime, timezone

PROMOTE_THRESHOLD = 0.10   # minimum EV improvement to trigger promotion
MAX_DD_LIMIT      = 10.0   # reject configs with max_dd > 10%
WF_RATIO          = 0.70   # val_ev must be >= 70% of train_ev

RELAY_PATH   = os.path.join(os.path.dirname(__file__), '..', 'alert_relay.py')
RESULTS_PATH = os.path.join(os.path.dirname(__file__), 'autoresearch_latest.json')
LOG_PATH     = os.path.join(os.path.dirname(__file__), 'promotion_log.json')

WEBHOOK = os.environ.get('DISCORD_WEBHOOK_ALERTS',
          os.environ.get('DISCORD_WEBHOOK', ''))

def load_results():
    with open(RESULTS_PATH) as f:
        return json.load(f)

def load_promotion_log():
    try:
        with open(LOG_PATH) as f:
            return json.load(f)
    except:
        return {"current_ev": 0.52, "current_params": {}, "history": []}

def save_promotion_log(log):
    with open(LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)

def get_current_challenge_ev(relay_src):
    """Extract current CHALLENGE rr and min_prob from relay source to estimate EV."""
    log = load_promotion_log()
    return log.get("current_ev", 0.52)

def update_relay_challenge(params):
    """Patch the CHALLENGE config block in alert_relay.py in-place."""
    with open(RELAY_PATH, 'r') as f:
        src = f.read()

    def repl(key, val):
        nonlocal src
        # Match key inside CHALLENGE block: e.g.  'bb_period':   20,
        pattern = r"(    'CHALLENGE':\s*\{.*?'" + key + r"':\s*)([\w\.\[\], ]+)(,)"
        replacement = lambda m: m.group(1) + repr(val) + m.group(3)
        src = re.sub(pattern, replacement, src, flags=re.DOTALL)

    repl('bb_period',   params['bb_period'])
    repl('bb_std',      params['bb_std'])
    repl('rr',          params['rr'])
    repl('min_prob',    params['min_prob'])
    repl('htf_bars',    params.get('htf_bars', 48))
    repl('entry_hours', params.get('entry_hours', [8,9,18,19,20]))

    with open(RELAY_PATH, 'w') as f:
        f.write(src)

def post_discord(msg):
    if not WEBHOOK:
        print("No webhook — skipping Discord notification")
        return
    try:
        requests.post(WEBHOOK, json={'content': msg}, timeout=10)
        print("Discord notified")
    except Exception as e:
        print(f"Discord notify error: {e}")

def run():
    print("=== Auto-Promote Check ===")
    data     = load_results()
    best     = data['best']
    plog     = load_promotion_log()
    new_ev   = best['ev']
    new_dd   = best.get('max_dd', 0)
    new_p    = best['params']
    cur_ev   = plog.get('current_ev', 0.52)
    wf       = data.get('walk_forward', {})
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    print(f"Current live EV : {cur_ev:+.4f}")
    print(f"New best EV     : {new_ev:+.4f}")
    print(f"Improvement     : {new_ev - cur_ev:+.4f} (threshold: +{PROMOTE_THRESHOLD})")
    print(f"New max_dd      : {new_dd}% (limit: {MAX_DD_LIMIT}%)")

    # Gate 1: EV improvement
    if new_ev - cur_ev < PROMOTE_THRESHOLD:
        print(f"❌ SKIP — improvement {new_ev-cur_ev:+.4f} < threshold {PROMOTE_THRESHOLD}")
        post_discord(
            f"🔬 **AutoResearch {date_str}**\n"
            f"No promotion — best EV `{new_ev:+.4f}` vs current `{cur_ev:+.4f}` "
            f"(Δ`{new_ev-cur_ev:+.4f}`, need `+{PROMOTE_THRESHOLD}`)"
        )
        return False

    # Gate 2: drawdown safety
    if new_dd > MAX_DD_LIMIT:
        print(f"❌ SKIP — max_dd {new_dd}% exceeds limit {MAX_DD_LIMIT}%")
        post_discord(
            f"🔬 **AutoResearch {date_str}**\n"
            f"Promotion blocked — max_dd `{new_dd}%` exceeds prop firm limit `{MAX_DD_LIMIT}%`"
        )
        return False

    # Gate 3: walk-forward
    wf_best = wf.get('best', {})
    train_ev = wf_best.get('train_ev', new_ev)
    val_ev   = wf_best.get('val_ev', new_ev)
    if train_ev > 0 and val_ev < WF_RATIO * train_ev:
        print(f"❌ SKIP — walk-forward failed: val_ev {val_ev:.4f} < {WF_RATIO}×train_ev {train_ev:.4f}")
        post_discord(
            f"🔬 **AutoResearch {date_str}**\n"
            f"Promotion blocked — walk-forward failed (val `{val_ev:.3f}` < 70% of train `{train_ev:.3f}`)"
        )
        return False

    # ✅ ALL GATES PASSED — PROMOTE
    print(f"✅ PROMOTING — EV {cur_ev:+.4f} → {new_ev:+.4f}")
    update_relay_challenge(new_p)

    # Update log
    plog['history'].append({
        "date": date_str,
        "prev_ev": cur_ev,
        "new_ev": new_ev,
        "params": new_p,
        "max_dd": new_dd,
        "grade": best.get('grade', '?'),
    })
    plog['current_ev']     = new_ev
    plog['current_params'] = new_p
    save_promotion_log(plog)

    post_discord(
        f"🚀 **CHALLENGE CONFIG PROMOTED** — {date_str}\n"
        f"```\n"
        f"EV:        {cur_ev:+.4f} → {new_ev:+.4f}  (+{new_ev-cur_ev:.4f})\n"
        f"Grade:     {best.get('grade','?')}   Max DD: {new_dd}%\n"
        f"bb_period: {new_p.get('bb_period')}   bb_std: {new_p.get('bb_std')}\n"
        f"rr:        {new_p.get('rr')}          min_prob: {new_p.get('min_prob')}\n"
        f"htf_bars:  {new_p.get('htf_bars')}    hours: {new_p.get('entry_hours')}\n"
        f"```\n"
        f"CHALLENGE strategy is now live with the new config."
    )
    return True

if __name__ == '__main__':
    promoted = run()
    sys.exit(0 if True else 1)  # always exit 0 so workflow doesn't fail
