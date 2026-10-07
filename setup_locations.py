#!/usr/bin/env python3
"""Build data/locations_id.csv for Q-Guard.

One-time setup: joins two public sources into a static city table.

  Coordinates + population : GeoNames dump Indonesia (ID.txt, CC BY 4.0)
                              http://download.geonames.org/export/dump/ID.zip
  Postal codes              : edwin/database-kodepos-seluruh-indonesia (tbl_kodepos.sql)
                              turunan data Kemendagri/Pos Indonesia, 80k+ kelurahan

Output: data/locations_id.csv
  city_id, name, bare_name, province, is_kota, latitude, longitude, population, postal_codes

Join rules (see AGENTS.md 4.1.1):
  - KAB. X and KOTA X are distinct entities; never merged into one row.
    (Limitation: postal source does not carry the Kab/Kota distinction, so when
    both entities share a bare name they share the postal pool. Coordinates and
    population remain separate. This is a source-data limitation, reported below.)
  - Normalization: case-fold, strip parenthetical suffixes, drop all
    spaces/hyphens/periods from the join key. Province names normalized
    (legacy names -> current, e.g. NANGGROE ACEH DARUSSALAM (NAD) -> ACEH).
  - Unmatched rows are reported, never silently dropped from the count.

Stdlib only. Run once; commit the CSV so the generator is offline thereafter.
"""

import csv
import io
import os
import re
import sys
import urllib.request
import zipfile

GEONAMES_URL = "http://download.geonames.org/export/dump/ID.zip"
ADMIN1_URL = "http://download.geonames.org/export/dump/admin1CodesASCII.txt"
KODEPOS_URL = (
    "https://raw.githubusercontent.com/edwin/database-kodepos-seluruh-indonesia/"
    "master/tbl_kodepos.sql"
)

RAW_DIR = "data/raw"
OUT_PATH = "data/locations_id.csv"

# GeoNames admin1 (province) English name -> current official Indonesian name.
# Verified against the 38 codes in admin1CodesASCII.txt.
PROVINCE_MAP = {
    "North Sumatra": "SUMATERA UTARA",
    "Aceh": "ACEH",
    "Yogyakarta": "DI YOGYAKARTA",
    "South Sumatra": "SUMATERA SELATAN",
    "West Sumatra": "SUMATERA BARAT",
    "North Sulawesi": "SULAWESI UTARA",
    "Southeast Sulawesi": "SULAWESI TENGGARA",
    "Central Sulawesi": "SULAWESI TENGAH",
    "South Sulawesi": "SULAWESI SELATAN",
    "Riau": "RIAU",
    "East Nusa Tenggara": "NUSA TENGGARA TIMUR",
    "West Nusa Tenggara": "NUSA TENGGARA BARAT",
    "Maluku": "MALUKU",
    "Lampung": "LAMPUNG",
    "East Kalimantan": "KALIMANTAN TIMUR",
    "Central Kalimantan": "KALIMANTAN TENGAH",
    "South Kalimantan": "KALIMANTAN SELATAN",
    "West Kalimantan": "KALIMANTAN BARAT",
    "East Java": "JAWA TIMUR",
    "Central Java": "JAWA TENGAH",
    "West Java": "JAWA BARAT",
    "Jambi": "JAMBI",
    "Jakarta": "DKI JAKARTA",
    "Papua": "PAPUA",
    "Bengkulu": "BENGKULU",
    "Bali": "BALI",
    "Banten": "BANTEN",
    "Gorontalo": "GORONTALO",
    "Bangka–Belitung Islands": "KEPULAUAN BANGKA BELITUNG",
    "North Maluku": "MALUKU UTARA",
    "West Papua": "PAPUA BARAT",
    "West Sulawesi": "SULAWESI BARAT",
    "Riau Islands": "KEPULAUAN RIAU",
    "North Kalimantan": "KALIMANTAN UTARA",
    "Southwest Papua": "PAPUA BARAT DAYA",
    "Central Papua": "PAPUA TENGAH",
    "Highland Papua": "PAPUA PEGUNUNGAN",
    "South Papua": "PAPUA SELATAN",
}


def download(url: str, dest: str) -> str:
    if os.path.exists(dest):
        print(f"[skip] {dest} already downloaded")
        return dest
    print(f"[down] {url}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    return dest


def norm_province(p: str) -> str:
    """Normalize province names from both sources to current official names."""
    p = p.upper().strip()
    p = re.sub(r"\s*\(NAD\)$", "", p)
    p = re.sub(r"^NANGGROE ACEH DARUSSALAM.*$", "ACEH", p)
    p = re.sub(r"\s*\((?:NTT|NTB)\)$", "", p)
    p = re.sub(r"^BANGKA BELITUNG$", "KEPULAUAN BANGKA BELITUNG", p)
    return p


def norm_key(name: str) -> str:
    """Join key: uppercase, strip parenthetical suffix, remove separators.

    Kab./Kota qualification must be handled by the caller BEFORE calling this,
    so that Kab. Bogor and Kota Bogor never collapse onto the same key from the
    GeoNames side.
    """
    name = name.upper().strip()
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name)  # "BOLAANG MONGONDOW (BOLMONG)"
    name = re.sub(r"^KABUPATEN\s+", "", name)
    name = re.sub(r"^KOTA\s+ADMINISTRASI\s+", "", name)
    name = re.sub(r"^KOTA\s+", "", name)
    name = re.sub(r"\s*REGENCY$", "", name)  # English form of Kabupaten
    name = re.sub(r"^ADMINISTRASI\s+", "", name)
    name = re.sub(r"[\s.\-]+", "", name)  # BAU-BAU->BAUBAU, BANYU ASIN->BANYUASIN
    return name


def parse_geonames(adm2_rows, admin1_path):
    """Extract ADM2 (kabupaten/kota) entries: coordinates, population, province."""
    # admin1CodesASCII.txt: "ID.<code>\t<english name>\t<ascii name>\t<geonameid>"
    admin1_en = {}
    with open(admin1_path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("ID."):
                code, en_name = line.rstrip("\n").split("\t")[:2]
                admin1_en[code[len("ID."):]] = en_name

    cities = []
    for f in adm2_rows:
        name, admin1 = f[1], f[10]
        prov = PROVINCE_MAP.get(admin1_en.get(admin1, ""), "").upper()
        if not prov:
            continue
        is_kota = bool(re.match(r"^Kota", name, re.IGNORECASE))
        key = norm_key(name)
        cities.append(
            {
                "name": name,
                "bare_name": re.sub(
                    r"^(?:Kabupaten|Kota Administrasi|Kota)\s+", "", name, flags=re.IGNORECASE
                ),
                "province": prov,
                "is_kota": is_kota,
                "key": key,
                "latitude": float(f[4]),
                "longitude": float(f[5]),
                "population": int(f[14]) if f[14] else 0,
            }
        )
    return cities


def parse_kodepos(sql_text):
    """Parse edwin tbl_kodepos.sql INSERTs -> {(key, prov): set(postal codes)}."""
    pools = {}
    rx = re.compile(
        r"INSERT INTO `tbl_kodepos` VALUES \('\d+', '[^']*', '[^']*', "
        r"'([^']*)', '([^']*)', '(\d{5})'\);"
    )
    for m in rx.finditer(sql_text):
        kab, prov, code = m.group(1), m.group(2), m.group(3)
        k = (norm_key(kab), norm_province(prov))
        pools.setdefault(k, set()).add(code)
    return pools


def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    # 1. GeoNames dump
    id_zip = download(GEONAMES_URL, os.path.join(RAW_DIR, "ID.zip"))
    admin1_txt = download(ADMIN1_URL, os.path.join(RAW_DIR, "admin1CodesASCII.txt"))
    with zipfile.ZipFile(id_zip) as z:
        with z.open("ID.txt") as fh:
            adm2_rows = [
                line.rstrip("\n").split("\t")
                for line in io.TextIOWrapper(fh, encoding="utf-8")
                if line.split("\t")[7] == "ADM2"
            ]
    print(f"[geonames] ADM2 entries: {len(adm2_rows)}")

    cities = parse_geonames(adm2_rows, os.path.join(RAW_DIR, "admin1CodesASCII.txt"))
    print(f"[geonames] parsed cities: {len(cities)}")

    # 2. Postal codes
    kodepos_sql = download(KODEPOS_URL, os.path.join(RAW_DIR, "tbl_kodepos.sql"))
    with open(kodepos_sql, encoding="latin-1") as fh:
        pools = parse_kodepos(fh.read())
    print(f"[kodepos] city pools: {len(pools)}")

    # 3. Join
    matched, unmatched_gn = [], []
    shared_pool_warn = []
    for c in cities:
        pool = pools.get((c["key"], c["province"]))
        if pool:
            matched.append((c, sorted(pool)))
        else:
            unmatched_gn.append((c["name"], c["province"]))

    # Kab/Kota sharing one postal pool (source limitation, not a merge):
    key_count = {}
    for c, _ in matched:
        key_count[(c["key"], c["province"])] = key_count.get((c["key"], c["province"]), 0) + 1
    shared_pool_warn = [k for k, n in key_count.items() if n > 1]

    matched_ed_keys = {(c["key"], c["province"]) for c, _ in matched}
    unmatched_ed = [k for k in pools if k not in matched_ed_keys]

    # 4. Write CSV
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "city_id", "name", "bare_name", "province", "is_kota",
                "latitude", "longitude", "population", "postal_codes",
            ]
        )
        for i, (c, pool) in enumerate(matched, 1):
            w.writerow(
                [
                    i, c["name"], c["bare_name"], c["province"], int(c["is_kota"]),
                    c["latitude"], c["longitude"], c["population"],
                    "|".join(pool),
                ]
            )

    # 5. Report
    print(f"\n[done] wrote {len(matched)} rows -> {OUT_PATH}")
    print(f"[report] geonames unmatched: {len(unmatched_gn)} / {len(cities)}")
    for name, prov in sorted(unmatched_gn):
        print(f"  GN-MISS {name} ({prov})")
    print(f"[report] kodepos pools unmatched: {len(unmatched_ed)} / {len(pools)}")
    for key, prov in sorted(unmatched_ed)[:20]:
        print(f"  ED-MISS {key} ({prov})")
    if shared_pool_warn:
        print(f"[warn] {len(shared_pool_warn)} bare-name pairs share one postal pool "
              "(Kab/Kota not distinguished by postal source):")
        for key, prov in sorted(shared_pool_warn):
            print(f"  SHARED {key} ({prov})")


if __name__ == "__main__":
    sys.exit(main())
