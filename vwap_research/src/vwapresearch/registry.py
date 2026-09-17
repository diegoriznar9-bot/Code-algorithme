"""Experiment registry: append-only log of every material experiment.

Purpose (mission §38, §91): keep an honest count of hypotheses, parameter
combinations and rejections so that final results can be deflated for
multiple testing and losing variants are not silently forgotten.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

REG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "experiments", "registry.csv")
FIELDS = ["id", "date_utc", "phase", "hypothesis", "dataset", "split",
          "params", "n_obs", "result", "decision", "reason"]


def log(phase: str, hypothesis: str, dataset: str, split: str, params: str,
        n_obs, result: str, decision: str, reason: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(REG_PATH)), exist_ok=True)
    new = not os.path.exists(REG_PATH)
    n_existing = 0 if new else max(0, sum(1 for _ in open(REG_PATH)) - 1)
    exp_id = f"E{n_existing + 1:04d}"
    with open(REG_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"id": exp_id,
                    "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "phase": phase, "hypothesis": hypothesis, "dataset": dataset,
                    "split": split, "params": params, "n_obs": n_obs,
                    "result": result, "decision": decision, "reason": reason})
    return exp_id
