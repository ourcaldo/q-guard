#!/usr/bin/env python3
"""Stage 4: simple user-merchant graph features (AGENTS.md 10.3).

Bipartite user-merchant graph from transactions, WITHOUT label leakage:
merchant risk proxy is derived from user BEHAVIOR signals (per-user
rule component scores), never from the generator's user_type labels.
This is the "simple graph features first, no GNN" step of the roadmap
and a legitimate way to activate the M component (AGENTS.md 6.3) from
transaction data alone.

Signal propagation (2 iterations of neighbor averaging):
  merchant_score  = mean A-behavior of the users who pay it
  user_m_score   = mean merchant_score of the merchants the user pays

A fronting merchant (many deposit-patterned payers) lights up; a family
shop (1-2 payers with ordinary behavior) stays dark. A user paying lit
merchants inherits light - that is the M evidence.

Input : output/tx_scores.parquet, output/user_scores.parquet, output/users.parquet
Output: output/user_scores.parquet (comp_M + updated pattern/final/alert),
        output/merchant_scores.parquet, output/GRAPH_REPORT.md
Run on: VM.
"""

import os

import numpy as np
import pandas as pd

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(BASE, "output")

# Pattern weights stay AS THEY WERE before graph (round-3 values) - M does
# not steal weight from any component. Instead M acts as a BONUS: users in
# the review zone (>=35) whose merchants light up get pushed up. This adds
# evidence without degrading users whose case rests on F/R/L/C.
W_PATTERN = {"F": 0.20, "R": 0.15, "L": 0.15, "C": 0.10, "A": 0.40}
M_BONUS_ZONE = 35.0   # pattern range where merchant evidence can push
M_BONUS_MAX = 10.0    # cap of the push
M_ITERS = 2
MIN_MERCHANT_PAYERS = 2   # a merchant paid by 1 user says nothing about the merchant
PATTERN_FLOOR = 48.0
ALERT_THRESHOLDS = {"monitor": 30.0, "needs_review": 45.0, "high_risk": 52.0}


def scale_component(x, lo, hi):
    return (100 * x.clip(0, 1).where(x.notna(), 0)).pipe(
        lambda s: s - lo).clip(0, hi - lo) * (100 / (hi - lo)) if False else (
        (100 * ((x - lo) / (hi - lo)).clip(0, 1)).fillna(0))


def main():
    tx = pd.read_parquet(os.path.join(OUT, "tx_scores.parquet"))
    us = pd.read_parquet(os.path.join(OUT, "user_scores.parquet"))
    users = pd.read_parquet(os.path.join(OUT, "users.parquet"))

    # Per-transaction deposit-evidence weight (recency d_i * T_i already in
    # user_risk; here we propagate the A-behavior view).
    per_user_a = us.set_index("user_id").comp_A

    # user x merchant edge weight = number of transactions
    edges = tx.groupby(["merchant_id", "user_id"]).size().rename("w").reset_index()

    # Iterative propagation
    merchant_score = pd.Series(dtype=float)
    user_m = pd.Series(dtype=float)
    # start: each user carries its comp_A as behavior seed
    seed = per_user_a.copy()
    current = seed
    for it in range(M_ITERS):
        e = edges.merge(current.rename("ubehav"), on="user_id", how="left")
        e["ubehav"] = e.ubehav.fillna(0) * np.sqrt(e.w)   # frequency weighting
        ms = e.groupby("merchant_id").apply(
            lambda d: d.ubehav.sum() / np.sqrt(d.w).sum() if len(d) >= 1 else 0.0,
            include_groups=False)
        ms = ms.fillna(0)
        # merchants paid by a single user provide no cross-user evidence
        payer_counts = edges.groupby("merchant_id").user_id.nunique()
        ms = ms.where(payer_counts >= MIN_MERCHANT_PAYERS, 0)
        merchant_score = ms
        u = edges.merge(ms.rename("mscore"), on="merchant_id", how="left")
        u["mscore"] = u.mscore.fillna(0) * np.sqrt(u.w)
        user_m = u.groupby("user_id").apply(
            lambda d: d.mscore.sum() / np.sqrt(d.w).sum() if len(d) else 0.0,
            include_groups=False)
        current = (user_m * 0.5 + seed * 0.5).fillna(0)

    us = us.set_index("user_id")
    us["m_raw"] = user_m

    # Rebuild pattern with ORIGINAL weights - M does not enter the weighted
    # sum. Instead M is an evidence BONUS: users already inside the review
    # zone whose merchants light up get pushed up to M_BONUS_MAX points.
    # Nobody enters review purely on merchant context - the user's own
    # pattern must already be elevated (AGENTS.md 3: single-signal no-verdict).
    comp_M = scale_component(us.m_raw, 20.0, 80.0)
    pattern = (W_PATTERN["F"] * us.comp_F + W_PATTERN["R"] * us.comp_R
               + W_PATTERN["L"] * us.comp_L + W_PATTERN["C"] * us.comp_C
               + W_PATTERN["A"] * us.comp_A)
    bonus = (comp_M / 100.0) * M_BONUS_MAX
    pattern_boosted = pattern + (bonus * (pattern >= M_BONUS_ZONE))

    blend = 0.60 * us.user_risk + 0.40 * pattern_boosted
    floor = pattern_boosted.where(pattern_boosted >= PATTERN_FLOOR, 0.0)
    final = pd.concat([blend, floor], axis=1).max(axis=1)

    us["pattern_score"] = pattern
    us["comp_M"] = comp_M
    us["final_user_risk"] = final

    def level(r):
        if r >= ALERT_THRESHOLDS["high_risk"]: return "high_risk"
        if r >= ALERT_THRESHOLDS["needs_review"]: return "needs_review"
        if r >= ALERT_THRESHOLDS["monitor"]: return "monitor"
        return "normal"
    us["alert_level"] = final.map(level)
    us = us.reset_index()

    # Merchant report
    merch_out = pd.DataFrame({
        "merchant_id": merchant_score.index,
        "graph_score": merchant_score.values,
        "payer_count": payer_counts.reindex(merchant_score.index).fillna(0).astype(int).values,
    })
    merch_tx = tx.groupby("merchant_id").size()
    merch_out["tx_count"] = merch_tx.reindex(merch_out.merchant_id).fillna(0).values

    us.to_parquet(os.path.join(OUT, "user_scores.parquet"), index=False)
    merch_out.to_parquet(os.path.join(OUT, "merchant_scores.parquet"), index=False)

    # Evaluation vs ground truth
    m = us.merge(users[["user_id", "user_type"]], on="user_id")
    lines = ["# Laporan Graph Features (Tahap 4)", ""]
    lines.append("Skor M dihitung dari perilaku antar-user per merchant, tanpa")
    lines.append("membaca label generator. Evaluasi vs ground truth:")
    lines.append("")
    lines.append("## comp_M & alert per tipe")
    lines.append("")
    lines.append("| tipe | n | comp_M mean | review+high |")
    lines.append("|---|---|---|---|")
    for t, d in m.groupby("user_type"):
        alert = d.alert_level.value_counts()
        rv = int(alert.get("needs_review", 0) + alert.get("high_risk", 0))
        lines.append(f"| {t} | {len(d)} | {d.comp_M.mean():.1f} | {rv} ({rv/len(d):.0%}) |")
    lines.append("")
    # merchant concentration view: risky merchants should have many payers
    top_m = merch_out.nlargest(20, "graph_score")
    lines.append("## Top-20 merchant by graph score (anonim)")
    lines.append("")
    lines.append("| merchant | graph_score | payers |")
    lines.append("|---|---|---|")
    for _, r in top_m.iterrows():
        lines.append(f"| {r.merchant_id} | {r.graph_score:.1f} | {r.payer_count} |")
    lines.append("")
    report = "\n".join(lines)
    with open(os.path.join(OUT, "GRAPH_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    print(report)


if __name__ == "__main__":
    main()
