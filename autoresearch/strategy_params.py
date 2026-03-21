"""
strategy_params.py — THE FILE THE AGENT EDITS
AutoResearch Gen 1 best: EV +1.429, Grade A, Net +$10,000
"""

PARAMS = {
    "bb_period":    20,
    "bb_std":       2.0,
    "rr":           4.0,      # upgraded from 2.8
    "htf_bars":     48,
    "min_prob":     0.35,     # upgraded from 0.25
    "entry_hours":  [8, 9, 18, 19, 20],
}

EXPERIMENT_LOG = [
    {"gen": 0, "ev": 0.52,  "grade": "A-", "net": 8320,  "params": {"bb_period":20,"bb_std":2.0,"rr":2.8,"htf_bars":48,"min_prob":0.25,"entry_hours":[8,9,18,19,20]}, "note": "baseline"},
    {"gen": 1, "ev": 1.155, "grade": "A",  "net": 13400, "params": {"bb_period":20,"bb_std":2.0,"rr":4.0,"htf_bars":48,"min_prob":0.25,"entry_hours":[8,9,18,19,20]}, "note": "rr=4.0 single param win"},
    {"gen": 2, "ev": 0.846, "grade": "A",  "net": 5920,  "params": {"bb_period":20,"bb_std":2.0,"rr":2.8,"htf_bars":48,"min_prob":0.35,"entry_hours":[8,9,18,19,20]}, "note": "min_prob=0.35 single param win"},
    {"gen": 3, "ev": 1.429, "grade": "A",  "net": 10000, "params": {"bb_period":20,"bb_std":2.0,"rr":4.0,"htf_bars":48,"min_prob":0.35,"entry_hours":[8,9,18,19,20]}, "note": "COMBO WIN: rr=4.0 + min_prob=0.35"},
]
