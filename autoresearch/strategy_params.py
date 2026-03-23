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

    {"gen": 4, "ev": 4.84, "grade": "A", "net": 9680.0, "wr": 80.0, "trades": 10, "date": "2026-03-22", "params": {"bb_period": 13, "bb_std": 2.5, "rr": 6.3, "htf_bars": 48, "min_prob": 0.44, "entry_hours": [8, 9, 18, 19, 20]}, "note": "nightly autoresearch 180D"},

    {"gen": 5, "ev": 4.84, "grade": "A", "net": 9680.0, "wr": 80.0, "trades": 10, "date": "2026-03-23", "params": {"bb_period": 13, "bb_std": 2.5, "rr": 6.3, "htf_bars": 48, "min_prob": 0.44, "entry_hours": [8, 9, 18, 19, 20]}, "note": "nightly autoresearch 180D"},
]