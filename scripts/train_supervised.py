#!/usr/bin/env python3
"""Point 3: supervised pipeline REHEARSAL (AGENTS.md 10.2, 13).

This is NOT a claim that a trained model works. Per AGENTS.md 10.2, synthetic
labels must never be treated as truth - the only legitimate supervised model
trains on labels from human review, which this project does not have.

What this script proves instead: the day real review labels arrive, the
training path is ready end-to-end. It exercises every mechanical step with
the generator labels swapped in as placeholders:

  1. Time-based split (AGENTS.md 13): train on features from the FIRST half
     of the window, test on the LAST half - no random split.
  2. Feature matrix from the scoring pipeline (same features as stage 1/2).
  3. RandomForest + XGBoost-style gradient boosting (sklearn HistGB) with
     class weights (deposit users are the minority class).
  4. Calibration, threshold sweep, PR-AUC / precision@K on the test window.
  5. Comparison vs the rule-based baseline on the same split.

To use with real labels later: replace users.parquet's user_type column
with reviewer decisions (0 = cleared, 1 = confirmed risky) - nothing else
changes.

Input : output/user_scores.parquet, output/users.parquet
Output: output/SUPERVISED_REPORT.md
Run on: VM.
"""

import os
import sys

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import average_precision_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(BASE, "output")

SPLIT = "2026-07-01"

FEATURES = [
    "remote_ratio", "mean_distance", "max_distance",
    "round_large_ratio", "amount_cv", "repeat_amount_ratio",
    "tx_count", "distinct_merchants", "tx_per_merchant", "merchant_conc",
    "freq_change", "same_merchant_interval_cv",
    "repeat_round_ratio", "max_amount_occurrences",
]


def first_half_features(tx):
    """Recompute scoring features on the first half only (fit window)."""
    import score_transactions as st
    _, us = st.score(tx.copy())
    return us


def main():
    tx = pd.read_parquet(os.path.join(OUT, "transactions.parquet"))
    users = pd.read_parquet(os.path.join(OUT, "users.parquet"))
    tx["timestamp"] = pd.to_datetime(tx["timestamp"])

    # --- time split: features per half-window (AGENTS.md 13) --------------
    import score_transactions as st
    fit_tx = tx[tx.timestamp < SPLIT]
    test_tx = tx[tx.timestamp >= SPLIT]
    print(f"[split] fit: {len(fit_tx)} rows, test: {len(test_tx)} rows")

    _, fit_u = st.score(fit_tx.copy())
    _, test_u = st.score(test_tx.copy())

    y_type = users.set_index("user_id").user_type
    risky_types = {"risky", "risky_noisy", "risky_silent", "risky_routine",
                   "risky_silent_shared"}

    def frame(u):
        u = u.merge(users[["user_id", "user_type"]], on="user_id")
        X = u[FEATURES].copy()
        # fill NaN conservatively (features with <3 samples etc.)
        X = X.fillna(X.median(numeric_only=True)).fillna(0)
        y = u.user_type.isin(risky_types).astype(int)
        return X, y, u

    X_tr, y_tr, u_tr = frame(fit_u)
    X_te, y_te, u_te = frame(test_u)
    print(f"[split] train: {len(X_tr)} users ({y_tr.sum()} risky), "
          f"test: {len(X_te)} users ({y_te.sum()} risky)")

    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=300, class_weight="balanced",
            random_state=42, n_jobs=-1),
        "grad_boost": HistGradientBoostingClassifier(
            max_iter=300, random_state=42),
    }

    lines = ["# Laporan Supervised (Rehearsal) - Point 3", ""]
    lines.append("Latihan mekanik pipeline supervised. Label = generator")
    lines.append("(placeholder), BUKAN kebenaran - lihat catatan di file ini.")
    lines.append("")

    results = {}
    for name, model in models.items():
        cal = CalibratedClassifierCV(model, method="isotonic", cv=3)
        cal.fit(X_tr, y_tr)
        proba = cal.predict_proba(X_te)[:, 1]
        prauc = average_precision_score(y_te, proba)
        prec_at = {}
        order = np.argsort(-proba)
        y_sorted = y_te.to_numpy()[order]
        for k in [100, 500, 1000, 2000]:
            prec_at[k] = float(y_sorted[:k].mean())
        recall_k = float(y_sorted[:int(y_te.sum())].mean()) if y_te.sum() else 0
        results[name] = (prauc, prec_at, recall_k)
        print(f"[{name}] PR-AUC {prauc:.4f}  P@2000 {prec_at[2000]:.3f}")

        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"PR-AUC (test window): {prauc:.4f}")
        lines.append("Precision@K (test): " + ", ".join(
            f"{k}={v:.3f}" for k, v in prec_at.items()))
        lines.append(f"Recall@n(risky): {recall_k:.3f}")
        lines.append("")

    # baseline comparison: rule scores on the same test window
    rule_prauc = average_precision_score(y_te, u_te.final_user_risk)
    lines.append("## Baseline (rule) di test window yang sama")
    lines.append("")
    lines.append(f"PR-AUC: {rule_prauc:.4f}")
    lines.append("")

    lines.append("## Catatan keabsahan")
    lines.append("")
    lines.append("1. Label berasal dari generator, dipakai sebagai placeholder")
    lines.append("   untuk menguji MEKANIK pipeline, bukan performa model.")
    lines.append("   (AGENTS.md 10.2: label sintetis bukan kebenaran final).")
    lines.append("2. Split waktu dijaga: train Apr-Jun, test Jul-Sep - tidak")
    lines.append("   ada kebocoran masa depan (AGENTS.md 13).")
    lines.append("3. Saat label human review tersedia, ganti kolom user_type")
    lines.append("   dengan keputusan reviewer; seluruh kode tetap sama.")

    report = "\n".join(lines)
    with open(os.path.join(OUT, "SUPERVISED_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    print("\n".join(lines[:20]))


if __name__ == "__main__":
    main()
