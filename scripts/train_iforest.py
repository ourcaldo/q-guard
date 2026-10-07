#!/usr/bin/env python3
"""Stage 2: Isolation Forest anomaly detection on user behavior features.

AGENTS.md 11 Tahap 2 / 10.1: train unsupervised on user-level behavior
features, compare anomaly_score against the rule-based score, evaluate both
against generator ground truth (evaluation only).

Input : output/user_scores.parquet (rule features + scores)
Output: output/iforest_scores.parquet, output/IFOREST_REPORT.md
Run on: VM (fits in memory easily)

Design notes:
- Features: the per-user behavior features from stage 1 (L/A/F/R/C raw
  features), NOT the rule scores themselves - the model must be an
  independent opinion.
- Robust scaling first (median/IQR) because features are heavy-tailed.
- contamination is set from the generator's risky share (2%) ONLY as a
  calibration starting point; the anomaly_score ranking is the real output
  and is evaluated across thresholds.
"""

import os

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(BASE, "output")

FEATURES = [
    "remote_ratio", "mean_distance", "max_distance",
    "round_large_ratio", "amount_cv", "repeat_amount_ratio",
    "tx_count", "distinct_merchants", "tx_per_merchant", "merchant_conc",
    "freq_change",
    # interaction: repeated round amounts are the deposit core pattern.
    # Distinguishes silent-local depositors from innocent bill payers whose
    # round amounts repeat only a couple of times a month.
    "repeat_round_ratio",
    "max_amount_occurrences",
]


def main():
    users = pd.read_parquet(os.path.join(OUT, "users.parquet"))
    scores = pd.read_parquet(os.path.join(OUT, "user_scores.parquet"))

    X = scores[FEATURES].copy()
    X = X.fillna(X.median(numeric_only=True))

    # Robust scaling: features are heavy-tailed (distances, counts)
    Xs = RobustScaler().fit_transform(X)

    # contamination 0.02 ~ generator risky share; ranking is what matters
    ifo = IsolationForest(n_estimators=300, contamination=0.02,
                          random_state=42, n_jobs=-1)
    ifo.fit(Xs)

    # decision_function: higher = more normal -> flip so higher = more anomalous
    anomaly = -ifo.decision_function(Xs)
    scores["iforest_anomaly"] = anomaly
    scores["iforest_flag"] = ifo.predict(Xs)  # -1 = outlier

    m = scores.merge(users[["user_id", "user_type"]], on="user_id")

    lines = ["# Laporan Isolation Forest (Tahap 2)", ""]
    lines.append("Unsupervised anomaly score vs rule score vs ground truth generator.")
    lines.append("")

    # per-type anomaly stats
    lines.append("## Anomaly score per tipe user")
    lines.append("")
    lines.append("| tipe | n | mean | p50 | p95 | flag(-1) |")
    lines.append("|---|---|---|---|---|---|")
    for t, d in m.groupby("user_type"):
        q = d.iforest_anomaly.quantile([.5, .95]).round(3).tolist()
        lines.append(f"| {t} | {len(d)} | {d.iforest_anomaly.mean():.3f} "
                     f"| {q[0]} | {q[1]} | {(d.iforest_flag == -1).sum()} |")
    lines.append("")

    # precision@K for iforest ranking vs rule ranking
    risky_mixed = m.user_type.isin(["risky", "mixed"])
    lines.append("## Precision@K: Isolation Forest vs Rule-based")
    lines.append("")
    lines.append("| K | iforest | rule |")
    lines.append("|---|---|---|")
    for k in [100, 500, 1000, 2000, 4000]:
        p_if = risky_mixed[m.nlargest(k, "iforest_anomaly").index].mean()
        p_ru = risky_mixed[m.nlargest(k, "final_user_risk").index].mean()
        lines.append(f"| {k} | {p_if:.3f} | {p_ru:.3f} |")
    lines.append("")

    # PR-AUC of each score against risky ground truth
    y_true = (m.user_type == "risky").astype(int).to_numpy()
    order = np.argsort(-m.iforest_anomaly.to_numpy())
    y_sorted = y_true[order]
    prec = np.cumsum(y_sorted) / np.arange(1, len(y_sorted) + 1)
    rec = np.cumsum(y_sorted) / max(y_sorted.sum(), 1)
    prauc_if = float((prec * np.diff(np.concatenate([[0], rec]))).sum())
    order2 = np.argsort(-m.final_user_risk.to_numpy())
    y_sorted2 = y_true[order2]
    prec2 = np.cumsum(y_sorted2) / np.arange(1, len(y_sorted2) + 1)
    rec2 = np.cumsum(y_sorted2) / max(y_sorted2.sum(), 1)
    prauc_ru = float((prec2 * np.diff(np.concatenate([[0], rec2]))).sum())
    lines.append("## PR-AUC (ground truth = risky)")
    lines.append("")
    lines.append(f"Isolation Forest: {prauc_if:.4f}")
    lines.append(f"Rule-based:       {prauc_ru:.4f}")
    lines.append("")

    # agreement between the two rankings at the top
    top_if = set(m.nlargest(4000, "iforest_anomaly").user_id)
    top_ru = set(m.nlargest(4000, "final_user_risk").user_id)
    lines.append("## Agreement top-4000")
    lines.append("")
    lines.append(f"overlap: {len(top_if & top_ru)} / 4000")
    lines.append("")

    scores.to_parquet(os.path.join(OUT, "iforest_scores.parquet"), index=False)
    with open(os.path.join(OUT, "IFOREST_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
