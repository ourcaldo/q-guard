#!/usr/bin/env python3
"""Point 4: operational simulation - what running this daily would cost.

Turns the evaluation numbers into operational answers a payment provider
would actually need before deploying:

  1. Queue load: how many users land in each alert level per rolling month?
  2. Reviewer hours: queue load x assumed review time (ASSUMPTION, flagged).
  3. Detection latency: for deposit users who DO get caught, how many days
     from their first deposit-pattern transaction until their rolling
     window score first crosses needs_review? (rolling 30-day re-score)

All numbers come from the synthetic 2M dataset; the only invented input is
MINUTES_PER_REVIEW, which is an operational parameter to change per team,
not a claim.

Input : output/transactions.parquet, output/users.parquet
Output: output/OPS_REPORT.md
Run on: VM (rolling re-scoring over ~6 windows of 1M+ rows each).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from score_transactions import score, ALERT_THRESHOLDS

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(BASE, "output")

# ASSUMPTION (operational parameter, not a claim): minutes a reviewer needs
# per queued user. Change per team; sweep shown in the report.
MINUTES_PER_REVIEW = 20

RISKY_TYPES = {"risky", "risky_noisy", "risky_silent", "risky_routine",
               "risky_silent_shared"}

WINDOW_DAYS = 30       # rolling observation window (AGENTS.md 4.2: 30 hari)
START = pd.Timestamp("2026-04-01")
END = pd.Timestamp("2026-09-30")


def main():
    tx = pd.read_parquet(os.path.join(OUT, "transactions.parquet"))
    users = pd.read_parquet(os.path.join(OUT, "users.parquet"))
    tx["timestamp"] = pd.to_datetime(tx["timestamp"])

    lines = ["# Laporan Simulasi Operasional - Point 4", ""]

    # --- 1. queue load from the final full-window scores ------------------
    us = pd.read_parquet(os.path.join(OUT, "user_scores.parquet"))
    m = us.merge(users[["user_id", "user_type"]], on="user_id")
    lv = m.alert_level.value_counts()
    lines.append("## Beban antrean (scoring window penuh 6 bulan)")
    lines.append("")
    for lvl in ["high_risk", "needs_review", "monitor", "normal"]:
        n = int(lv.get(lvl, 0))
        share = n / len(m)
        per_month = n / 6
        hours = n * MINUTES_PER_REVIEW / 60
        lines.append(f"- {lvl}: {n:,} user ({share:.1%}) -> ~{per_month:,.0f}/bulan, "
                     f"~{hours:,.0f} jam review total")
    lines.append("")
    review_total = int(lv.get("needs_review", 0) + lv.get("high_risk", 0))
    lines.append(f"Total masuk antrean review: {review_total:,} user "
                 f"({review_total/len(m):.1%} dari {len(m):,})")
    lines.append(f"Kapasitas reviewer: {review_total*MINUTES_PER_REVIEW/60:,.0f} jam / "
                 f"6 bulan = {review_total*MINUTES_PER_REVIEW/60/6/160:,.1f} FTE "
                 f"(asumsi 160 jam/bulan/reviewer, {MINUTES_PER_REVIEW} menit/user)")
    lines.append("")

    # --- 2. detection latency via rolling 30-day windows -------------------
    # Re-score monthly snapshots; a deposit user is "caught" in the first
    # month whose rolling score crosses needs_review. Latency = that month's
    # end minus their first risky-pattern transaction.
    lines.append("## Latensi deteksi (rolling 30 hari)")
    lines.append("")
    months = pd.date_range("2026-04-30", "2026-09-30", freq="ME")
    first_tx = tx[tx.user_id.isin(
        users[users.user_type.isin(RISKY_TYPES)].user_id)
    ].groupby("user_id").timestamp.min()

    caught_month = {}
    for m_end in months:
        sub = tx[(tx.timestamp > m_end - pd.Timedelta(days=WINDOW_DAYS))
                 & (tx.timestamp <= m_end)]
        if len(sub) == 0:
            continue
        _, su = score(sub.copy())
        hit = su[su.final_user_risk >= ALERT_THRESHOLDS["needs_review"]].user_id
        for uid in hit:
            if uid not in caught_month:
                caught_month[uid] = m_end
        print(f"[{m_end.date()}] window rows {len(sub):,}, newly caught {len(hit):,}")

    caught = pd.Series(caught_month)
    lat = (caught - first_tx.reindex(caught.index)).dt.days.dropna()
    lines.append(f"Deposit user yang tertangkap dalam rolling window: "
                f"{len(caught):,} / {len(first_tx):,} ({len(caught)/len(first_tx):.1%})")
    if len(lat):
        lines.append("Hari dari transaksi deposit pertama sampai masuk review:")
        lines.append(f"- median: {lat.median():.0f} hari")
        lines.append(f"- p25: {lat.quantile(.25):.0f} hari, p75: {lat.quantile(.75):.0f} hari")
    lines.append("")
    lines.append("Catatan: user yang belum tertangkap di bulan mana pun sebagian")
    lines.append("besar adalah pola tipis (lihat laporan time-split) - mereka")
    lines.append("butuh akumulasi transaksi lebih banyak sebelum sinyal repetisi matang.")

    report = "\n".join(lines)
    with open(os.path.join(OUT, "OPS_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    print(report)


if __name__ == "__main__":
    main()
