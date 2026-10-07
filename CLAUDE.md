# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Q-Guard is a prototype system for detecting anomalous QRIS (Indonesian QR payment standard) user behavior patterns associated with online gambling deposits. The system outputs **risk scores and alerts for human investigation** — it never automatically concludes that a user is gambling. The payer (user) is the primary analysis unit; merchants serve only as transaction context.

`AGENTS.md` is the authoritative design document. It defines the full system architecture, risk signal definitions (L/A/M/B/F/R/C), scoring formulas, alert thresholds, ML roadmap (rule-based → Isolation Forest → supervised → graph features), evaluation strategy, and data governance constraints. Read it before making design decisions.

## Current Stage

Stage 1 (data synthesis + rule-based baseline). No production code exists yet. Planned pipeline:

```
setup_locations.py   → one-time: build data/locations_id.csv (city, province, lat, lon, population, postal pool) 
                        from GeoNames ID.zip + Kemendagri postal code repo, joined by (city, province)
generate_data.py      → parametric synthetic QRIS transaction data (--n-users --n-tx --seed), output parquet
scoring               → rule-based per AGENTS.md §7-8, then Isolation Forest anomaly detection (§10.1)
```

## Development Commands

Planned environment: single VPS (Ubuntu 24.04, 8 vCPU / 32 GB RAM — see VM.md, **do not push VM.md to GitHub**).

```bash
python -m venv .venv && source .venv/bin/activate
pip install numpy pandas pyarrow scikit-learn
python setup_locations.py                    # one-time, needs network (GeoNames + Kemendagri data)
python generate_data.py --n-users 10000 --n-tx 100000 --seed 42   # dev smoke test
python generate_data.py --n-users 200000 --n-tx 2000000 --seed 42 # full simulation run
```

## Architecture Decisions (from AGENTS.md — binding constraints)

- **Scoring**: transaction score `T_i = 0.30·L + 0.25·A + 0.20·M + 0.25·B` (all components 0–100). User risk = 0.60·recency-weighted transaction average + 0.40·pattern score. Alerts: `T_i ≥ 90` immediate; user `≥ 60` review. Weights/thresholds are starting points requiring calibration.
- **Labels**: synthetic "risky user" types exist only as generator ground truth for evaluation. The pipeline treats all data as unlabeled (Stage 1 anomaly/rule-based). Synthetic labels must never be treated as truth for supervised training.
- **Location data**: city name is the generation basis; coordinates are jitter around city centers (never random points). Two-source join rule: `KAB. X` and `KOTA X` are different administrative entities and must never be merged during normalization. Setup must report unmatched rows.
- **Merchant modeling**: merchant count is an emergent output of per-city merchant registries and per-user merchant pools, not a direct input. User types have distinct pool behaviors (risky users pay few merchants repetitively — that repetition is the signal).
- **MCC**: raw data stores 4-digit `merchant_mcc` (QR tag 52, ISO 18245, per EMVCo standard adopted by BI in PADG 21/16/PADG/2019). Model features use a derived low-cardinality `merchant_category` enum via static mapping (~20-30 MCCs, rest → `other`).
- **Identity fields** (`merchant_pan`, `cpan`, `rrn`, `nmid`): QRIS receipt identity fields, generated for realism but **never usable as risk features**.
- **Excluded signals** (by design): time-of-day as a primary signal, single cross-city payment, small amounts alone, transaction counts alone. See AGENTS.md §16.
- **Evaluation**: time-based splits only (no random splits), metrics beyond accuracy (precision/recall/PR-AUC/Precision@K). See AGENTS.md §13.
- **Privacy**: location data processed at minimum granularity; see AGENTS.md §15 (UU 27/2022 PDP, OJK 8/2023).

## Git & GitHub Rules

- Repository: q-guard on GitHub under the account tied to **ourcaldo@gmail.com**.
- **All commits and PRs must use only the user's own identity** — never include any AI or Claude attribution (no `Co-Authored-By: Claude`, no "Generated with Claude Code" lines).
- **VM.md must never be committed or pushed** (contains VPS credentials).
- **Edit only on this local machine.** The workflow is: edit locally → commit → push to GitHub → pull on the VM. Never edit code directly on the VM.
- **Never run heavy commands on this local machine** (training, full data generation, or anything memory-intensive). This local machine has only 4 GB RAM — all heavy work (generation of large datasets, model training, large experiments) runs on the VM (see VM.md). Local is only for editing, small smoke checks, and git operations.

## Language

The user communicates in Indonesian (casual). AGENTS.md and docs are written in Indonesian; code, identifiers, and comments follow standard English conventions.
