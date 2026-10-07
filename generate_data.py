#!/usr/bin/env python3
"""Generate synthetic QRIS transaction data for Q-Guard.

Reads data/locations_id.csv (from setup_locations.py) and produces:
  data/merchants.parquet   - merchant registry (one row per merchant, fixed attributes)
  data/transactions.parquet- synthetic QRIS transactions per AGENTS.md 4.1.1
  data/users.parquet       - user registry with generator ground-truth type

User types (AGENTS.md 4.1.1, distribution over users not transactions):
  normal   85%  local, varied amounts, sensible categories
  heavy     7%  power user, frequent but healthy pattern
  remote    5%  pays across 2 cities (work/family) - false positive test
  risky     2%  repeated same amounts, remote, spike, topup/game merchants
  mixed     1%  normal plus occasional risky pattern

Merchant count is an EMERGENT output: each city holds a merchant registry;
user pools sample from it (shared popular merchants), new merchants are
created only when a pool needs one. Registry is seeded per city proportional
to population before the first user pool is built.

Identity fields (merchant_pan, cpan, rrn, transaction_id, order_id, nmid,
terminal_id) are generated for realism only and must never be used as risk
features (AGENTS.md 4.1.1).

Dependencies: pandas, pyarrow, numpy (VM). Small runs (<1M tx) also fine locally.
"""

import argparse
import math
import os
import random
import uuid

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- constants

SEED_DEFAULT = 42

USER_TYPE_SHARES = [
    ("normal", 0.85),
    ("heavy", 0.07),
    ("remote", 0.05),
    ("risky", 0.02),
    ("mixed", 0.01),
]

# Mean transactions per user over the 6-month window, by type.
TX_PER_USER = {"normal": 10, "heavy": 60, "remote": 14, "risky": 45, "mixed": 12}

# Share of a user's transactions that are "risky-pattern" for mixed users.
MIXED_RISKY_SHARE = 0.3

# Merchant pool size per user type.
POOL_SIZE = {"normal": 10, "heavy": 30, "remote": 14, "risky": 3, "mixed": 10}

# MCC -> category mapping (subset; rest -> other). AGENTS.md 4.1.1.
MCC_MAP = {
    "5812": "food_beverage", "5814": "food_beverage", "5912": "food_beverage",
    "5411": "retail_grocery", "5331": "retail_grocery", "5921": "retail_grocery",
    "4111": "transportation", "4121": "transportation", "5541": "transportation",
    "4900": "utilities",
    "5732": "game_topup", "5734": "game_topup", "7994": "game_topup",
    "8398": "donation", "8651": "donation",
    "7922": "ticket", "7991": "ticket",
    "7372": "digital_service", "4816": "digital_service",
    "7941": "entertainment", "5816": "entertainment",
    "7297": "family_transfer", "8299": "family_transfer",
}

# Category weights for NORMAL context merchants.
CATEGORY_W = {
    "food_beverage": 0.30, "retail_grocery": 0.22, "transportation": 0.12,
    "utilities": 0.08, "donation": 0.04, "ticket": 0.04,
    "digital_service": 0.06, "entertainment": 0.06, "family_transfer": 0.08,
}
# Risky merchants concentrate here.
RISKY_CATEGORY_W = {"game_topup": 0.55, "digital_service": 0.35, "entertainment": 0.10}

AMOUNT_BY_CATEGORY = {  # (low, typical_high) rupiah, log-uniform within range
    "food_beverage": (1000, 150000), "retail_grocery": (2000, 400000),
    "transportation": (2000, 50000), "utilities": (10000, 500000),
    "donation": (1000, 100000), "ticket": (25000, 500000),
    "digital_service": (5000, 200000), "entertainment": (5000, 250000),
    "family_transfer": (20000, 500000), "game_topup": (10000, 100000),
    "other": (5000, 200000),
}
RISKY_AMOUNT_SET = [25000, 50000, 100000, 200000]  # repeated exact amounts

JITTER_KM = 3.0  # coordinate jitter around city center
MAX_AMOUNT = 10_000_000  # BI limit per QRIS transaction

ISSUERS = ["BCA", "Mandiri", "BNI", "BRI", "GoPay", "OVO", "DANA", "ShopeePay", "LinkAja"]
ACQUIRERS = ["BCA", "Mandiri", "BRI", "Xendit", "Midtrans", "DOKU"]

WINDOW_DAYS = 183  # 6 months: 2026-04-01 .. 2026-09-30 (AGENTS.md 13 time split)

USER_TYPES = [t for t, _ in USER_TYPE_SHARES]
USER_WEIGHTS = [w for _, w in USER_TYPE_SHARES]


# ---------------------------------------------------------------- helpers

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def jitter_coord(rng, lat, lon, km=JITTER_KM):
    dlat = rng.uniform(-km, km) / 111.0
    dlon = rng.uniform(-km, km) / (111.0 * math.cos(math.radians(lat)) or 1.0)
    return round(lat + dlat, 6), round(lon + dlon, 6)


def amount_for(rng, category, risky=False):
    if risky:
        return float(rng.choice(RISKY_AMOUNT_SET))
    lo, hi = AMOUNT_BY_CATEGORY.get(category, AMOUNT_BY_CATEGORY["other"])
    return float(round(10 ** rng.uniform(math.log10(lo), math.log10(hi)), -2))


# ---------------------------------------------------------------- merchants

class MerchantRegistry:
    """Per-city merchant registry. New merchants are created on demand;
    popular merchants get sampled repeatedly by different users."""

    def __init__(self, city, rng):
        self.city = city          # dict row from locations_id.csv
        self.rng = rng
        self.rows = []

    def create(self, risky=False):
        w = RISKY_CATEGORY_W if risky else CATEGORY_W
        cats = list(w)
        weights = [w[c] for c in cats]
        category = self.rng.choices(cats, weights=weights)[0]
        mcc = next((k for k, v in MCC_MAP.items() if v == category), "5732")
        mid = f"M{self.city['city_id']:04d}{len(self.rows):05d}"
        lat, lon = jitter_coord(self.rng, float(self.city["latitude"]),
                                float(self.city["longitude"]))
        postal = self.rng.choice(self.city["postal_codes"].split("|"))
        self.rows.append({
            "merchant_id": mid,
            "merchant_name": f"Merchant {mid}",
            "nmid": f"ID{self.rng.randrange(10**13, 10**14)}",
            "merchant_pan": f"9360{self.rng.randrange(10**15):015d}",
            "terminal_id": f"{self.rng.choice('ABCDEFGH')}{self.rng.randrange(10, 99):02d}",
            "mcc": mcc,
            "category": category,
            "city": self.city["name"],
            "province": self.city["province"],
            "latitude": lat,
            "longitude": lon,
            "postal_code": postal,
            "country": "ID",
            "acquirer": self.rng.choice(ACQUIRERS),
            "is_risky_merchant": risky,
        })
        return self.rows[-1]

    def sample(self, n, risky=False):
        """Sample n merchants, creating fresh ones when the registry runs low.
        Popular (low index) merchants are resampled with boosted probability."""
        pool_risky = [r for r in self.rows if r["is_risky_merchant"] == risky]
        while len(pool_risky) < n:
            pool_risky.append(self.create(risky=risky))
        # popularity weighting: earlier-created merchants are more popular
        idx = list(range(len(pool_risky)))
        w = [1.0 / (1 + 0.05 * i) for i in idx]
        picks = set()
        while len(picks) < n:
            picks.add(self.rng.choices(idx, weights=w)[0])
        return [pool_risky[i] for i in sorted(picks)]


# ---------------------------------------------------------------- generation

def generate(n_users, n_tx, seed, out_dir):
    if n_users <= 0 or n_tx < n_users:
        raise SystemExit("--n-tx must be >= --n-users")

    loc = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "data", "locations_id.csv"))
    # keep cities with population > 0; big cities drive the distribution
    loc = loc[loc.population > 0].copy().reset_index(drop=True)
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)

    # user types
    types = list(nprng.choice(USER_TYPES, size=n_users, p=[w for w in USER_WEIGHTS]))

    # users: home city weighted by population
    city_w = loc["population"].to_numpy(dtype=float)
    home_idx = nprng.choice(len(loc), size=n_users, p=city_w / city_w.sum())

    # --- pass 1: user definitions (home + optional second city for remote)
    users = []
    for i in range(n_users):
        u = {
            "user_id": f"U{i:07d}",
            "user_type": types[i],
            "home_city_idx": int(home_idx[i]),
            "cpan": f"9360{rng.randrange(10**15):015d}",
            "issuer": rng.choice(ISSUERS),
        }
        if u["user_type"] == "remote":
            j = int(nprng.choice(len(loc), p=city_w / city_w.sum()))
            u["remote_city_idx"] = int(j) if j != u["home_city_idx"] else int((j + 1) % len(loc))
        users.append(u)

    # transactions per user, scaled so the total matches n_tx
    base = np.array([TX_PER_USER[t] for t in types], dtype=float)
    n_tx_user = np.maximum(
        np.round(base * (n_tx / base.sum()) * nprng.uniform(0.5, 1.5, size=n_users)), 1
    ).astype(int)
    # fix rounding drift toward n_tx
    diff = n_tx - int(n_tx_user.sum())
    if diff > 0:
        bump = rng.sample(range(n_users), diff)
        for b in bump:
            n_tx_user[b] += 1

    # registries
    registries = {}
    for idx, row in loc.iterrows():
        registries[idx] = MerchantRegistry(row.to_dict(), rng)

    # risky users also pay risky merchants in remote cities
    risky_city_count = 6
    risky_cities = loc[loc.population > 1_000_000].nlargest(risky_city_count, "population").index.tolist()

    tx_rows = []
    for i, u in enumerate(users):
        ureg = [registries[u["home_city_idx"]]]
        if u["user_type"] == "remote":
            ureg.append(registries[u["remote_city_idx"]])
        pool_size = POOL_SIZE[u["user_type"]]
        # risky users: small pool of risky merchants in one big remote city
        risky_pool = None
        if u["user_type"] in ("risky",):
            rc = rng.choice(risky_cities)
            risky_pool = registries[rc].sample(POOL_SIZE["risky"], risky=True)
        elif u["user_type"] == "mixed":
            rc = rng.choice(risky_cities)
            risky_pool = registries[rc].sample(2, risky=True)

        local_pool = ureg[0].sample(pool_size)
        if len(ureg) > 1:
            local_pool += ureg[1].sample(pool_size)

        n = int(n_tx_user[i])
        # timestamps spread over the window; risky users cluster later (spike)
        if u["user_type"] == "risky":
            days = nprng.choice(np.arange(int(WINDOW_DAYS * 0.5), WINDOW_DAYS), size=n)
        else:
            days = nprng.integers(0, WINDOW_DAYS, size=n)
        ts = pd.Timestamp("2026-04-01").value + days * 86400 * 10**9
        ts += nprng.integers(0, 86400, size=n) * 10**9  # random time of day (not a signal)
        ts = pd.to_datetime(np.sort(ts))

        for k in range(n):
            is_risky_tx = risky_pool is not None and (
                u["user_type"] == "risky"
                or (u["user_type"] == "mixed" and rng.random() < MIXED_RISKY_SHARE)
            )
            if is_risky_tx:
                m = risky_pool[rng.randrange(len(risky_pool))]
            else:
                if u["user_type"] == "remote" and rng.random() < 0.4 and len(ureg) > 1:
                    reg = ureg[1]
                else:
                    reg = ureg[0]
                m = local_pool[rng.randrange(len(local_pool))]

            # Payer location = user's home city (AGENTS.md 6.1: L measures the
            # difference between user location and merchant location). For
            # normal local payments the distance stays small; risky and remote
            # payments produce large distances through the merchant side.
            home = loc.iloc[u["home_city_idx"]]
            payer_lat, payer_lon = jitter_coord(rng, float(home["latitude"]),
                                                float(home["longitude"]))
            payer_city = home["name"]

            amt = amount_for(rng, m["category"], risky=is_risky_tx)
            amt = min(amt, MAX_AMOUNT)
            status = "success" if rng.random() > 0.04 else "failed"

            tx_rows.append({
                "transaction_id": f"{ts[k].strftime('%Y%m%d%H%M%S')}{u['user_id'][1:]}{k:04d}",
                "rrn": f"{rng.randrange(10**12):012d}",
                "merchant_pan": m["merchant_pan"],
                "cpan": u["cpan"],
                "terminal_id": m["terminal_id"],
                "order_id": str(uuid.UUID(int=rng.getrandbits(128))),
                "timestamp": ts[k],
                "user_id": u["user_id"],
                "merchant_id": m["merchant_id"],
                "amount": amt,
                "merchant_mcc": m["mcc"],
                "merchant_name": m["merchant_name"],
                "merchant_city": m["city"],
                "merchant_postal_code": m["postal_code"],
                "merchant_country": "ID",
                "merchant_latitude": m["latitude"],
                "merchant_longitude": m["longitude"],
                "payer_city": payer_city,
                "payer_latitude": payer_lat,
                "payer_longitude": payer_lon,
                "issuer_name": u["issuer"],
                "acquirer_name": m["acquirer"],
                "status": status,
            })

    tx = pd.DataFrame(tx_rows)
    tx = tx.sort_values("timestamp").reset_index(drop=True)

    merchants = pd.DataFrame(
        [r for reg in registries.values() for r in reg.rows]
    ).drop_duplicates("merchant_id").reset_index(drop=True)

    users_df = pd.DataFrame(
        [{
            "user_id": u["user_id"],
            "user_type": u["user_type"],  # ground truth, evaluation only
            "cpan": u["cpan"],
            "issuer": u["issuer"],
        } for u in users]
    )

    os.makedirs(out_dir, exist_ok=True)
    tx.to_parquet(os.path.join(out_dir, "transactions.parquet"), index=False)
    merchants.to_parquet(os.path.join(out_dir, "merchants.parquet"), index=False)
    users_df.to_parquet(os.path.join(out_dir, "users.parquet"), index=False)

    # sanity summary
    dist = tx.groupby("user_id").size()
    print(f"[done] users: {len(users_df)}  merchants: {len(merchants)}  tx: {len(tx)}")
    print(f"[done] tx/user: mean={dist.mean():.1f} min={dist.min()} max={dist.max()}")
    print(f"[done] user types: {dict(users_df.user_type.value_counts())}")
    dist_km = tx.apply(
        lambda r: haversine_km(r.payer_latitude, r.payer_longitude,
                               r.merchant_latitude, r.merchant_longitude), axis=1
    ) if len(tx) <= 200_000 else None
    if dist_km is not None:
        print(f"[done] payer-merchant distance km: mean={dist_km.mean():.1f} "
              f"median={dist_km.median():.1f} >50km share={(dist_km > 50).mean():.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-users", type=int, default=10_000)
    ap.add_argument("--n-tx", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=SEED_DEFAULT)
    ap.add_argument("--out-dir", default="data")
    a = ap.parse_args()
    generate(a.n_users, a.n_tx, a.seed, a.out_dir)


if __name__ == "__main__":
    main()
