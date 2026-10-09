#!/usr/bin/env python3
"""Point 2: honest time-split evaluation (AGENTS.md 13).

All previous runs calibrated thresholds and evaluated on the SAME full
6-month window - in-sample. This script splits time in half:

  Fit window   : Apr-Jun 2026 (first 3 months)  -> calibrate thresholds
  Test window  : Jul-Sep 2026 (last 3 months)   -> apply them untouched

Procedure (label-free calibration, same spirit as the pipeline):
  1. Score users on the fit window only (features recomputed on fit data).
  2. Pick thresholds as quantiles of the fit score distribution:
     monitor / needs_review / high_risk at the same population shares the
     calibrated full-window thresholds produced (measured on fit window).
  3. Score users on the test window with features recomputed on test data.
  4. Apply the FIT thresholds to TEST scores. Evaluate vs ground truth.

The result answers: do the thresholds transfer across time? If recall/FP
hold, the numbers in our reports are trustworthy. If they collapse, the
full-window results were partly in-sample luck.

Input : output/transactions.parquet, output/users.parquet
Output: output/TIMESPLIT_REPORT.md
Run on: VM (scoring runs twice on ~1M-row halves).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from score_transactions import score, ALERT_THRESHOLDS, PATTERN_FLOOR

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(BASE, "output")

SPLIT = "2026-07-01"


def apply_levels(final):
    def level(r):
        if r >= ALERT_THRESHOLDS["high_risk"]: return "high_risk"
        if r >= ALERT_THRESHOLDS["needs_review"]: return "needs_review"
        if r >= ALERT_THRESHOLDS["monitor"]: return "monitor"
        return "normal"
    return final.map(level)


def main():
    tx = pd.read_parquet(os.path.join(OUT, "transactions.parquet"))
    users = pd.read_parquet(os.path.join(OUT, "users.parquet"))

    tx["timestamp"] = pd.to_datetime(tx["timestamp"])
    fit_tx = tx[tx.timestamp < SPLIT]
    test_tx = tx[tx.timestamp >= SPLIT]
    print(f"[split] fit rows: {len(fit_tx)}, test rows: {len(test_tx)}")

    # 1. score each window independently
    fit_tx_s, fit_users = score(fit_tx.copy())
    test_tx_s, test_users = score(test_tx.copy())

    # 2. thresholds: quantiles that reproduce the full-window population
    # shares (measured on this fit window) - label-free
    q = fit_users.final_user_risk.quantile([0.98, 0.995, 0.999])
    fit_thresh = {
        "monitor": float(fit_users.final_user_risk.quantile(0.90)),
        "needs_review": float(q.iloc[0]),
        "high_risk": float(q.iloc[2]),
    }
    print(f"[fit] thresholds from fit window: {fit_thresh}")

    # 3. apply fit thresholds to test scores + evaluate both windows
    def eval_frame(u, thresh, tag):
        def level(r):
            if r >= thresh["high_risk"]: return "high_risk"
            if r >= thresh["needs_review"]: return "needs_review"
            if r >= thresh["monitor"]: return "monitor"
            return "normal"
        u = u.copy()
        u["alert_level"] = u.final_user_risk.map(level)
        m = u.merge(users[["user_id", "user_type"]], on="user_id")
        rows = []
        for t, d in m.groupby("user_type"):
            alert = d.alert_level.value_counts()
            rv = int(alert.get("needs_review", 0) + alert.get("high_risk", 0))
            rows.append((t, len(d), rv, rv / len(d)))
        return rows

    fit_rows = eval_frame(fit_users, fit_thresh, "fit")
    test_rows = eval_frame(test_users, fit_thresh, "test")

    lines = ["# Laporan Time-Split (Point 2 - AGENTS.md 13)", ""]
    lines.append(f"Fit: < {SPLIT} (Apr-Jun), Test: >= {SPLIT} (Jul-Sep).")
    lines.append("Threshold dikalibrasi di fit window, dipakai mentah di test.")
    lines.append("")
    lines.append(f"Threshold fit-window (kuantil): { {k: round(v,1) for k,v in fit_thresh.items()} }")
    lines.append("")
    for tag, rows in [("FIT (Apr-Jun)", fit_rows), ("TEST (Jul-Sep)", test_rows)]:
        lines.append(f"## {tag}")
        lines.append("")
        lines.append("| tipe | n | review+high | % |")
        lines.append("|---|---|---|---|")
        for t, n, rv, pct in sorted(rows, key=lambda r: r[0]):
            lines.append(f"| {t} | {n} | {rv} | {pct:.1%} |")
        lines.append("")

    report = "\n".join(lines)
    with open(os.path.join(OUT, "TIMESPLIT_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    print(report)


if __name__ == "__main__":
    main()
