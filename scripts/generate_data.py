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

# User types. The "adversarial" types exist to keep the evaluation honest
# (see docs/ASSUMPTIONS.md): without them the synthetic data is too easy and
# every detector scores near-perfect, which proves nothing.
USER_TYPE_SHARES = [
    ("normal", 0.74),
    ("heavy", 0.07),
    ("remote", 0.05),
    ("risky", 0.02),
    ("mixed", 0.01),
    # adversarial types - hardening round 1
    ("risky_noisy", 0.03),   # gambling pattern but messy: odd amounts, wider pool
    ("normal_hard", 0.02),   # innocent but looks risky: round recurring payments, some remote
    ("risky_silent", 0.01),  # only ONE dimention is off (e.g. repeated amounts only)
    # adversarial types - hardening round 4 (attack the round-3 assumptions)
    ("risky_routine", 0.01),     # gambling deposits on a SCHEDULE (recreational
                                 # bettor with a weekly ritual) - breaks the
                                 # "deposits are scattered" assumption
    ("normal_hard_random", 0.02),# innocent recurring round payments at RANDOM
                                 # times (buy when needed, not on payday) -
                                 # breaks the "recurring = scheduled" assumption
    # adversarial types - round 5 (attack the graph/M assumptions)
    ("risky_silent_shared", 0.01),  # silent depositors who share the SAME
                                    # local fronting merchant with many other
                                    # depositors - the realistic fronting-shop
                                    # pattern (PPATK: merchant misuse; AUSTRAC
                                    # 17.3a: deposits via local POS)
    ("normal_collective", 0.01),    # innocents paying recurring round dues to
                                    # ONE shared local merchant together
                                    # (iuran/arusan/koperasi) - attacks the
                                    # "lit merchant = fronting" assumption
]

# Mean transactions per user over the 6-month window, by type.
TX_PER_USER = {"normal": 10, "heavy": 60, "remote": 14, "risky": 45, "mixed": 12,
               "risky_noisy": 45, "normal_hard": 20, "risky_silent": 40,
               "risky_routine": 30, "normal_hard_random": 20,
               "risky_silent_shared": 40, "normal_collective": 15}

# Share of a user's transactions that are "risky-pattern" for mixed users.
MIXED_RISKY_SHARE = 0.3

# Merchant pool size per user type.
POOL_SIZE = {"normal": 10, "heavy": 30, "remote": 14, "risky": 3, "mixed": 10,
             "risky_noisy": 8, "normal_hard": 10, "risky_silent": 4,
             "risky_routine": 3, "normal_hard_random": 10,
             "risky_silent_shared": 3, "normal_collective": 3}

# Round 5: shared fronting merchants. Created lazily per city; depositors and
# collective-due payers each cluster onto a few shared merchants in their own
# home city, mimicking one shop fronting many payers (or one shop collecting
# dues for many innocent neighbours).
SHARED_FRONTING_PER_CITY = 3

# Adversarial behaviour knobs.
RISKY_NOISY_ROUND_SHARE = 0.45   # only some deposits are round amounts
NORMAL_HARD_ROUND_SHARE = 0.50   # half of payments are round 50k multiples
NORMAL_HARD_REMOTE_SHARE = 0.20  # some payments to a distant city (family)

# MCC -> PJSP-style business category. The enum follows what real PJSPs use in
# QRIS merchant onboarding (DANA Bisnis: kedai makanan/minuman, toko retail,
# usaha jasa, usaha rumahan/online; Xendit/Midtrans use similar coarse sets).
# We keep 4 coarse categories and map MCCs into them; unknown MCC -> other.
MCC_MAP = {
    "5812": "food_beverage", "5814": "food_beverage", "5912": "food_beverage",
    "5411": "retail", "5331": "retail", "5921": "retail",
    "4111": "services", "4121": "services", "5541": "services",
    "4900": "services", "7922": "services", "7991": "services",
    "7372": "services", "4816": "services", "7941": "services",
    "5732": "services", "5734": "services", "7994": "services",
    "8398": "services", "8651": "services",
    "7297": "services", "8299": "services", "5816": "services",
}

# Category weights for ALL merchants, risky or not. In reality merchants pick
# (or mis-pick) categories independent of whether they receive gambling
# deposits - a deposit-fronting merchant shows up as a warung or retail shop.
# Category is therefore never a risk signal in this system.
# Weights are an assumption: only "food/retail dominate (93% MSMEs)" is
# grounded (BI SI-2025 press release); exact shares are not published.
CATEGORY_W = {
    "food_beverage": 0.40, "retail": 0.35, "services": 0.20, "other": 0.05,
}

AMOUNT_BY_CATEGORY = {  # (low, typical_high) rupiah, log-uniform within range
    "food_beverage": (1000, 150000), "retail": (2000, 400000),
    "services": (2000, 500000), "other": (5000, 200000),
}

# Round-amount behaviour (grounded in domain knowledge, not a fixed "risky set"):
# gambling deposits overwhelmingly use round multiples of 50k (50k, 100k, 150k,
# 200k, ...) and rarely odd values - but NOT exclusively:
#  - normal users also pay round amounts (bills, services)
#  - gambling users occasionally deposit odd amounts
# The A signal must therefore be statistical (share of repeated large round
# amounts), never "round amount = gambling".
ROUND_PAYMENT_CATEGORIES = {"services"}
ROUND_PAYMENT_SHARE = 0.40          # share of those categories paid in round 50k multiples
RISKY_ROUND_SHARE = 0.85             # share of gambling deposits that are round
RISKY_DEPOSIT_GRID = [50_000, 100_000, 150_000, 200_000, 250_000,
                      300_000, 400_000, 500_000, 750_000, 1_000_000]

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


def amount_for(rng, category, risky=False, user_type="normal"):
    """Amounts: log-uniform per category, snapped to 100s (real merchant prices).
    Both sides get round amounts - normal users via bill-like recurring payments
    and utility bills, gambling users via the deposit grid. The overlap is the
    point: roundness alone never decides anything."""
    round_cat = category in ROUND_PAYMENT_CATEGORIES
    if risky:
        share = {"risky_noisy": RISKY_NOISY_ROUND_SHARE,
                 "risky_silent": RISKY_ROUND_SHARE}.get(user_type, RISKY_ROUND_SHARE)
        if rng.random() < share:
            return float(rng.choice(RISKY_DEPOSIT_GRID))
    elif user_type in ("normal_hard", "normal_hard_random"):
        if rng.random() < NORMAL_HARD_ROUND_SHARE:
            return float(rng.choice(RISKY_DEPOSIT_GRID))
    elif round_cat and rng.random() < ROUND_PAYMENT_SHARE:
        return float(rng.choice(RISKY_DEPOSIT_GRID))
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
        self.fronting_rows = []   # dedicated shared/fronting merchants

    def create_fronting(self):
        """A merchant outside the popularity pool - dedicated fronting shops
        used only by round-5 shared payers, so their payer mix is not
        diluted by ordinary users."""
        m = self.create()
        self.fronting_rows.append(m)
        return m

    def create(self):
        w = CATEGORY_W
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
        })
        return self.rows[-1]

    def sample(self, n):
        """Sample n merchants, creating fresh ones when the registry runs low.
        Popular (low index) merchants are resampled with boosted probability.
        All users draw from the same registry - there is no risky-merchant
        subset because merchant category says nothing about transaction risk."""
        while len(self.rows) < n:
            self.create()
        idx = list(range(len(self.rows)))
        w = [1.0 / (1 + 0.05 * i) for i in idx]
        picks = set()
        while len(picks) < n:
            picks.add(self.rng.choices(idx, weights=w)[0])
        return [self.rows[i] for i in sorted(picks)]


# ---------------------------------------------------------------- generation

def generate(n_users, n_tx, seed, out_dir):
    if n_users <= 0 or n_tx < n_users:
        raise SystemExit("--n-tx must be >= --n-users")

    loc = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "data", "locations_id.csv"))
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
    shared_pools = {}
    for i, u in enumerate(users):
        ureg = [registries[u["home_city_idx"]]]
        if u["user_type"] == "remote":
            ureg.append(registries[u["remote_city_idx"]])
        pool_size = POOL_SIZE[u["user_type"]]
        # Risky/mixed users pay a small merchant pool in one big remote city,
        # drawn from the SAME per-city registry everyone else uses.
        risky_pool = None
        if u["user_type"] in ("risky", "risky_noisy"):
            rc = rng.choice(risky_cities)
            risky_pool = registries[rc].sample(POOL_SIZE[u["user_type"]])
        elif u["user_type"] == "risky_silent":
            # silent risky: LOCAL merchants, small pool (4) with repeated round
            # deposits - frequent & scattered (PPATK "kecil, berulang,
            # tersebar"), only the A/R signals present, no distance signal
            risky_pool = ureg[0].sample(POOL_SIZE["risky_silent"])
        elif u["user_type"] == "normal_hard":
            # hard normal: innocent user with a family/errand pattern in ONE
            # distant city + round recurring amounts. Gets a remote pool
            # like the remote type but fewer transactions there.
            rc = rng.choice(risky_cities)
            risky_pool = registries[rc].sample(6)
        elif u["user_type"] == "risky_routine":
            # scheduled gambler: same remote-city deposit pool as risky,
            # but on a weekly ritual
            rc = rng.choice(risky_cities)
            risky_pool = registries[rc].sample(POOL_SIZE["risky_routine"])
        elif u["user_type"] == "normal_hard_random":
            # innocent recurring round payments to a LOCAL merchant at random
            # times - attacks the "recurring = scheduled" assumption
            risky_pool = ureg[0].sample(6)
        elif u["user_type"] in ("risky_silent_shared", "normal_collective"):
            # Round 5: payers cluster onto a few SHARED merchants in their own
            # city. Crucially these are DEDICATED shared merchants, created
            # outside the normal per-city registry sampling - a real fronting
            # shop serves many depositors but not the general public, and a
            # dues-collecting merchant serves its members only. Drawing from
            # the general registry would dilute the cross-user signal with
            # ordinary payers.
            key = ("shared", u["home_city_idx"])
            if key not in shared_pools:
                reg = registries[u["home_city_idx"]]
                while len(reg.fronting_rows) < SHARED_FRONTING_PER_CITY:
                    reg.create_fronting()
                shared_pools[key] = reg.fronting_rows[:]
            risky_pool = shared_pools[key]
        elif u["user_type"] == "mixed":
            rc = rng.choice(risky_cities)
            risky_pool = registries[rc].sample(2)

        local_pool = ureg[0].sample(pool_size)
        if len(ureg) > 1:
            local_pool += ureg[1].sample(pool_size)

        n = int(n_tx_user[i])
        # Timestamps: all types get an even base spread over the window.
        # Risky users additionally get one of three shapes, mirroring reality -
        # not every gambling user starts slow:
        #   "steady"  : dense deposits from the start (addict pattern)
        #   "spike"   : normal first, surge later (new gambler)
        #   "burst"   : short intense episode somewhere in the window
        days = nprng.integers(0, WINDOW_DAYS, size=n)
        if u["user_type"] == "risky":
            shape = rng.choice(["steady", "spike", "burst"])
            if shape == "steady":
                pass  # base uniform spread is already dense
            elif shape == "spike":
                days = nprng.choice(np.arange(int(WINDOW_DAYS * 0.5), WINDOW_DAYS), size=n)
            else:  # burst: a random ~3-week intense episode
                start = rng.randrange(0, WINDOW_DAYS - 21)
                days = nprng.integers(start, start + 21, size=n)
        elif u["user_type"] == "normal_hard":
            # Recurring family/business payments are SCHEDULED: roughly one
            # payment per month at a stable day, plus small jitter. This is
            # the honest opposite of the deposit pattern (PPATK 17.3
            # "kecil, berulang, tersebar" = frequent & scattered) and gives
            # interval-regularity features something real to separate on.
            gap = max(WINDOW_DAYS // max(n, 1), 1)
            starts = np.arange(n) * gap
            days = starts + nprng.normal(0, 2, size=n)  # ~2-day jitter
            days = np.clip(days, 0, WINDOW_DAYS - 1)
        elif u["user_type"] == "risky_routine":
            # Gambling deposits on a weekly ritual (recreational bettor:
            # AUSTRAC 17.3a lists frequency changes as an indicator; regular
            # weekend betting is a documented recreational pattern). Breaks
            # the round-3 "scattered timing" assumption from the OTHER side.
            weeks = WINDOW_DAYS // 7
            week_slots = nprng.integers(0, weeks, size=n)
            day_in_week = rng.randrange(7)  # one stable weekday per user
            days = week_slots * 7 + day_in_week + nprng.normal(0, 0.5, size=n)
            days = np.clip(days, 0, WINDOW_DAYS - 1)
        # normal_hard_random keeps the uniform random spread above: innocent
        # recurring round payments at random times (buys when needed).
        ts = pd.Timestamp("2026-04-01").value + days * 86400 * 10**9
        ts += nprng.integers(0, 86400, size=n) * 10**9  # random time of day (not a signal)
        ts = pd.to_datetime(np.sort(ts))

        for k in range(n):
            if u["user_type"] in ("risky", "risky_noisy", "risky_silent",
                                  "risky_routine", "risky_silent_shared"):
                is_risky_tx = True
            elif u["user_type"] == "mixed":
                is_risky_tx = rng.random() < MIXED_RISKY_SHARE
            elif u["user_type"] in ("normal_hard", "normal_hard_random"):
                is_risky_tx = rng.random() < NORMAL_HARD_REMOTE_SHARE
            else:
                is_risky_tx = False
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

            amt = amount_for(rng, m["category"], risky=is_risky_tx,
                             user_type=u["user_type"])
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
    ap.add_argument("--out-dir", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "output"))
    a = ap.parse_args()
    generate(a.n_users, a.n_tx, a.seed, a.out_dir)


if __name__ == "__main__":
    main()
