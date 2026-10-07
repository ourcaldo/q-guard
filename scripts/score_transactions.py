#!/usr/bin/env python3
"""Stage 1 rule-based scoring for Q-Guard (AGENTS.md 7-9).

Input : output/transactions.parquet, output/users.parquet
Output: output/tx_scores.parquet, output/user_scores.parquet,
        output/SCORING_REPORT.md

Pipeline:
  1. per-transaction features: distance, remote flag, round-amount,
     deviation from the user's own baseline
  2. per-user aggregate features (AGENTS.md 6: L, A, F, R, C)
  3. transaction score T_i = wL*L + wA*A + wB*B  (M omitted per 6.3:
     no valid merchant risk score; weights renormalized from 0.30/0.25/0.25)
  4. UserRisk = recency-weighted mean of T_i
  5. PatternScore = 0.30 F + 0.25 R + 0.25 L + 0.20 C
  6. FinalUserRisk = 0.60 UserRisk + 0.40 PatternScore
  7. alert level per 9: <40 normal, 40-59 monitor, 60-79 needs_review, >=80 high_risk

All components are on a 0-100 scale. Weights and thresholds are AGENTS.md
starting points - calibration comes later (docs/ASSUMPTIONS.md).
"""

import os

import numpy as np
import pandas as pd

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(BASE, "output")

# --- scoring weights (AGENTS.md 7-8, M removed and renormalized) ------------
W_TX = {"L": 0.30 / 0.80, "A": 0.25 / 0.80, "B": 0.25 / 0.80}
# Pattern weights, round 2: A (amount anomaly incl. repetition) enters the
# pattern score directly - repeated round deposits are deposit-core evidence
# even when location and merchant signals are absent (risky_silent case).
W_PATTERN = {"F": 0.20, "R": 0.15, "L": 0.15, "C": 0.10, "A": 0.40}
W_FINAL_USER = 0.60
W_FINAL_PATTERN = 0.40

REMOTE_KM = 50.0          # beyond this a payment counts as remote (L signal)
ROUND_MULTIPLE = 50_000   # round-amount grid multiple
RECENT_WEIGHTS = {        # recency quartile -> weight for UserRisk (AGENTS.md 8.1)
    0: 1.0, 1: 2.0, 2: 3.0, 3: 4.0,
}

# Alert thresholds, calibrated on the 2M-tx synthetic run (2026-10-07).
# AGENTS.md 9 starting points (40/60/80) sit too high for the score scale this
# component set produces: risky scores cluster at p50=53.5, p95=60.1 while
# normal users cap below 20. Sweep chosen for: risky recall >= 0.91 at
# needs_review, 0 remote-FP inflation that matters, normal FP = 0.
# ponytail: recalibrate when components change or real data arrives.
ALERT_THRESHOLDS = {"monitor": 30.0, "needs_review": 45.0, "high_risk": 52.0}
PATTERN_FLOOR = 48.0  # pattern score that alone justifies review (see score())


def haversine_np(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def clip01(s):
    return s.clip(0, 1)


def build_features(tx: pd.DataFrame) -> pd.DataFrame:
    """Per-transaction features."""
    tx = tx.copy()
    tx["distance_km"] = haversine_np(
        tx.payer_latitude, tx.payer_longitude,
        tx.merchant_latitude, tx.merchant_longitude)
    tx["is_remote"] = (tx.distance_km > REMOTE_KM).astype(int)
    tx["is_round"] = (tx.amount % ROUND_MULTIPLE == 0).astype(int)
    tx["is_round_large"] = ((tx.amount % ROUND_MULTIPLE == 0)
                            & (tx.amount >= ROUND_MULTIPLE)).astype(int)
    return tx


def per_user_features(tx: pd.DataFrame) -> pd.DataFrame:
    """Aggregate features per user_id (AGENTS.md 6)."""
    g = tx.groupby("user_id")
    f = pd.DataFrame(index=g.size().index)

    # L - location mismatch
    f["remote_ratio"] = g.is_remote.mean()
    f["mean_distance"] = g.distance_km.mean()
    f["max_distance"] = g.distance_km.max()

    # A - amount pattern
    f["round_large_ratio"] = g.is_round_large.mean()
    f["amount_cv"] = g.amount.std() / g.amount.mean()          # variasi nominal
    # share of transactions whose exact amount was paid more than once
    def repeated_share(d):
        vc = d.value_counts()
        return (vc[vc > 1].sum() / vc.sum()) if len(vc) else 0.0
    f["repeat_amount_ratio"] = tx.groupby("user_id").amount.apply(repeated_share)
    # interaction features for stage 2: repeated ROUND amounts (deposit core)
    def repeat_round(d):
        round_d = d[d % ROUND_MULTIPLE == 0]
        if len(round_d) == 0:
            return 0.0
        vc = round_d.value_counts()
        return float(vc[vc > 1].sum() / vc.sum())
    f["repeat_round_ratio"] = tx.groupby("user_id").amount.apply(repeat_round)
    # single most-repeated amount count (catches grid-deposit even if varied)
    f["max_amount_occurrences"] = tx.groupby("user_id").amount.apply(
        lambda d: int(d.value_counts().max()) if len(d) else 0)

    # F - frequency
    f["tx_count"] = g.size()

    # R - repetition (merchant concentration)
    f["distinct_merchants"] = g.merchant_id.nunique()
    f["tx_per_merchant"] = f.tx_count / f.distinct_merchants
    def merchant_conc(d):
        vc = d.value_counts(normalize=True)
        return float((vc ** 2).sum())
    f["merchant_conc"] = tx.groupby("user_id").merchant_id.apply(merchant_conc)

    # C - behavior change: second half vs first half of the user's own window
    tx_sorted = tx.sort_values("timestamp")
    n_per_user = tx_sorted.groupby("user_id").user_id.transform("size")
    seq = tx_sorted.groupby("user_id").cumcount()
    tx_sorted["is_second_half"] = (seq >= n_per_user // 2).astype(int)
    second = tx_sorted[tx_sorted.is_second_half == 1].groupby("user_id").size()
    first = tx_sorted[tx_sorted.is_second_half == 0].groupby("user_id").size()
    f["freq_change"] = (second / first.clip(lower=1)).fillna(1.0)

    return f


def scale_component(x, lo, hi):
    """Map a raw feature onto a 0-100 component score."""
    return (100 * clip01((x - lo) / (hi - lo))).fillna(0)


def score(tx: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tx = build_features(tx)

    # user baselines for B (deviation of a single tx from the user's own habit)
    g = tx.groupby("user_id")
    tx["user_median_amount"] = g.amount.transform("median")
    tx["user_median_distance"] = g.distance_km.transform("median")
    # how many times this exact amount appears in the user's history
    tx["amt_occurrences"] = tx.groupby(["user_id", "amount"]).amount.transform("size")

    # --- per-transaction component scores (0-100) ----------------------
    # L_i: remote payments are inherently more notable; within-remote,
    # larger distances raise the score.
    tx["L_i"] = np.where(
        tx.is_remote == 1,
        60 + 40 * clip01((tx.distance_km - REMOTE_KM) / 1500),
        20 * clip01(tx.distance_km / REMOTE_KM),
    )
    # A_i: round large amount, repeated in the user's own history, deviating
    # from their typical amount. The repeat count is what catches local
    # deposit patterns that have no other signal.
    amt_dev = tx.amount / tx.user_median_amount
    tx["A_i"] = (
        35 * tx.is_round_large
        + 35 * clip01((tx.amt_occurrences - 1) / 4)
        + 30 * clip01(np.log10(amt_dev.clip(lower=0.01)))
    ).clip(0, 100)
    # B_i: transaction deviates from the user's own distance & amount profile
    dist_dev = tx.distance_km / tx.user_median_distance.clip(lower=1.0)
    tx["B_i"] = (
        50 * clip01(dist_dev / 20)
        + 50 * clip01(np.log10(amt_dev.clip(lower=0.01)))
    ).clip(0, 100)

    # --- transaction score ----------------------------------------------
    tx["T_i"] = (W_TX["L"] * tx.L_i + W_TX["A"] * tx.A_i + W_TX["B"] * tx.B_i)

    # --- user-level features & pattern score -----------------------------
    f = per_user_features(tx)

    comp = pd.DataFrame(index=f.index)
    comp["L"] = scale_component(f.remote_ratio, 0.0, 0.8)
    # A: amount anomaly. repeat_amount_ratio is the core deposit signal -
    # share of transactions whose exact amount repeats. High repeat (>=0.4)
    # with round amounts is nearly exclusive to deposit patterns; a mild
    # repeat alone (e.g. normal_hard paying a monthly bill) must NOT flag.
    comp["A"] = (
        scale_component(f.repeat_amount_ratio, 0.0, 0.6) * 0.45
        + scale_component(f.round_large_ratio, 0.05, 0.7) * 0.35
        + (100 * clip01(1 - f.amount_cv.fillna(1) / 1.5)) * 0.20
    ).clip(0, 100)
    comp["F"] = scale_component(np.log10(f.tx_count.clip(lower=1)), 0.3, 1.8)
    comp["R"] = (scale_component(f.merchant_conc, 0.1, 0.7) * 0.5
                 + scale_component(f.tx_per_merchant.clip(lower=1), 2, 40) * 0.5).clip(0, 100)
    comp["C"] = scale_component(f.freq_change, 0.5, 2.0)

    pattern_score = (W_PATTERN["F"] * comp.F + W_PATTERN["R"] * comp.R
                     + W_PATTERN["L"] * comp.L + W_PATTERN["C"] * comp.C
                     + W_PATTERN["A"] * comp.A)

    # --- UserRisk: recency-weighted average of T_i ------------------------
    tx["ts_rank"] = tx.groupby("user_id").timestamp.rank(pct=True)
    tx["d_i"] = tx.ts_rank.map(lambda p: RECENT_WEIGHTS[min(3, int(p * 4))])
    wr = tx.assign(wT=tx.d_i * tx.T_i).groupby("user_id")
    user_risk = wr.wT.sum() / wr.d_i.sum()

    # Final = weighted blend, but a strong pattern must be able to carry a user
    # into review on its own: a local deposit pattern (repeated round amounts)
    # produces low per-transaction scores while the pattern is unmistakable.
    # Conditional floor at PATTERN_FLOOR (pattern >= 48 -> final >= pattern):
    # silent-risky patterns sit at p50 ~51 while normal-hard p75 ~45, so the
    # floor is selective by construction. Calibrated on smoke data 2026-10-08.
    blend = W_FINAL_USER * user_risk + W_FINAL_PATTERN * pattern_score
    floor = pattern_score.where(pattern_score >= PATTERN_FLOOR, 0.0)
    final = pd.concat([blend, floor], axis=1).max(axis=1).rename("final_user_risk")

    out_users = pd.concat(
        [final.rename("final_user_risk"),
         pattern_score.rename("pattern_score"),
         user_risk.rename("user_risk"),
         comp.add_prefix("comp_"), f],
        axis=1).reset_index()

    def level(r):
        if r >= ALERT_THRESHOLDS["high_risk"]: return "high_risk"
        if r >= ALERT_THRESHOLDS["needs_review"]: return "needs_review"
        if r >= ALERT_THRESHOLDS["monitor"]: return "monitor"
        return "normal"
    out_users["alert_level"] = out_users.final_user_risk.map(level)

    return tx, out_users


def evaluate(users: pd.DataFrame, scores: pd.DataFrame) -> str:
    """Compare scores against generator ground truth (evaluation only)."""
    m = scores.merge(users[["user_id", "user_type"]], on="user_id")
    lines = ["# Laporan Scoring Tahap 1", ""]
    lines.append("Skor rule-based vs ground truth generator (evaluasi saja).")
    lines.append("")
    lines.append("## Mean FinalUserRisk per tipe user")
    lines.append("")
    lines.append("| tipe | n | mean final | mean T-user | pattern |")
    lines.append("|---|---|---|---|---|")
    for t, d in m.groupby("user_type"):
        lines.append(
            f"| {t} | {len(d)} | {d.final_user_risk.mean():.1f} "
            f"| {d.user_risk.mean():.1f} | {d.pattern_score.mean():.1f} |")
    lines.append("")
    lines.append("## Distribusi alert level per tipe")
    lines.append("")
    lv = m.groupby(["user_type", "alert_level"]).size().unstack(fill_value=0)
    lv["total"] = lv.sum(axis=1)
    for lvl in ["normal", "monitor", "needs_review", "high_risk"]:
        if lvl not in lv.columns:
            lv[lvl] = 0
    lines.append("| tipe | normal | monitor | needs_review | high_risk | total |")
    lines.append("|---|---|---|---|---|---|")
    for utype, row in lv.iterrows():
        lines.append(f"| {utype} | {row['normal']} | {row['monitor']} | "
                     f"{row['needs_review']} | {row['high_risk']} | {row['total']} |")
    lines.append("")
    # precision@K: of the top-K scored users, how many are risky/mixed?
    topk = m.nlargest(2000, "final_user_risk")
    hits = topk.user_type.isin(["risky", "mixed"]).mean()
    lines.append(f"## Precision@2000 (top-2000 skor tertinggi)")
    lines.append("")
    lines.append(f"proporsi risky+mixed: {hits:.3f}")
    lines.append("")
    # false positives: remote users landing in high_risk
    remote_hi = m[(m.user_type == "remote") & (m.alert_level == "high_risk")]
    lines.append(f"## False positive check")
    lines.append("")
    lines.append(f"remote_user di high_risk: {len(remote_hi)} / "
                 f"{(m.user_type == 'remote').sum()} "
                 f"(harusnya mendekati 0 - jarak jauh sendirian bukti tidak cukup, AGENTS.md 3/16)")
    lines.append("")
    return "\n".join(lines)


def main():
    tx = pd.read_parquet(os.path.join(OUT, "transactions.parquet"))
    users = pd.read_parquet(os.path.join(OUT, "users.parquet"))
    tx_scored, user_scores = score(tx)
    tx_scored.to_parquet(os.path.join(OUT, "tx_scores.parquet"), index=False)
    user_scores.to_parquet(os.path.join(OUT, "user_scores.parquet"), index=False)
    report = evaluate(users, user_scores)
    with open(os.path.join(OUT, "SCORING_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    print(report)


if __name__ == "__main__":
    main()
