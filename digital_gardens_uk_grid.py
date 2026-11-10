#!/usr/bin/env python3
"""Digital Gardens North Tyne - GB grid data downloader (standard library only).

    python digital_gardens_uk_grid.py                 # 2018-2025 (default)
    python digital_gardens_uk_grid.py --years 2024    # quick one-year test

Downloads, in 7-day chunks, with resume:
  1. NESO Carbon Intensity API - North East England region (regionid 4):
     half-hourly forecast intensity (gCO2/kWh) and generation mix (%).
  2. NESO Carbon Intensity API - national half-hourly actual + forecast intensity.
  3. Elexon Insights - Market Index Data (MID) half-hourly wholesale price (GBP/MWh).

Output: Digital_Gardens_UK_GRID_<first>_<last>_DATA.zip  -> upload this file.
Attribution: National Energy System Operator (NESO) Carbon Intensity API, CC BY 4.0;
Elexon BMRS Insights Solution (BSC open data licence).
"""
from __future__ import annotations
import argparse, csv, datetime as dt, gzip, json, sys, time, urllib.error, urllib.request, zipfile
from pathlib import Path

CI = "https://api.carbonintensity.org.uk"
ELEXON = "https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index"
REGION_ID = 4  # North East England
UA = {"User-Agent": "DigitalGardensGridData/1.0 (research)", "Accept": "application/json"}


def get(url: str, attempts: int = 6):
    for n in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {e.code} for {url}") from e
            msg = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            msg = str(e)
        pause = min(4 * 2 ** n, 60)
        print(f"  retry in {pause}s ({msg})", flush=True)
        time.sleep(pause)
    raise RuntimeError(f"Failed after {attempts} attempts: {url}")


def chunks(first: int, last: int, days: int = 7):
    t = dt.datetime(first, 1, 1, tzinfo=dt.timezone.utc)
    end = dt.datetime(last + 1, 1, 1, tzinfo=dt.timezone.utc)
    while t < end:
        u = min(t + dt.timedelta(days=days), end)
        yield t, u
        t = u


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%MZ")


def cached(path: Path, url: str):
    if path.exists():
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            path.unlink()
    data = get(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    tmp.replace(path)
    time.sleep(0.2)
    return data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--years", default="2018:2025")
    p.add_argument("--output", default="Digital_Gardens_UK_GRID")
    p.add_argument("--skip-prices", action="store_true")
    a = p.parse_args()
    b = a.years.split(":"); first, last = int(b[0]), int(b[-1])
    out = Path(a.output).resolve(); raw = out / "raw"; out.mkdir(parents=True, exist_ok=True)
    log = {"retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "years": [first, last],
           "region_id": REGION_ID, "errors": []}
    reg_rows, nat_rows, px_rows = [], [], []
    spans = list(chunks(first, last))
    for i, (t0, t1) in enumerate(spans, 1):
        tag = t0.strftime("%Y%m%d")
        print(f"[{i}/{len(spans)}] {t0.date()} .. {t1.date()}", flush=True)
        # Regional (North East England)
        try:
            d = cached(raw / "regional" / f"{tag}.json.gz",
                       f"{CI}/regional/intensity/{iso(t0)}/{iso(t1)}/regionid/{REGION_ID}")
            for e in d.get("data", {}).get("data", []):
                mix = {m["fuel"]: m["perc"] for m in e.get("generationmix", [])}
                reg_rows.append([e["from"], e["to"], e["intensity"].get("forecast"), e["intensity"].get("index")]
                                + [mix.get(k) for k in FUELS])
        except Exception as ex:  # keep going; logged
            log["errors"].append(f"regional {tag}: {ex}")
        # National
        try:
            d = cached(raw / "national" / f"{tag}.json.gz", f"{CI}/intensity/{iso(t0)}/{iso(t1)}")
            for e in d.get("data", []):
                nat_rows.append([e["from"], e["to"], e["intensity"].get("forecast"), e["intensity"].get("actual")])
        except Exception as ex:
            log["errors"].append(f"national {tag}: {ex}")
        # Wholesale price
        if not a.skip_prices:
            try:
                d = cached(raw / "price" / f"{tag}.json.gz",
                           f"{ELEXON}?from={iso(t0)}&to={iso(t1)}&dataProviders=APXMIDP&format=json")
                for e in d.get("data", []):
                    px_rows.append([e.get("startTime"), e.get("settlementDate"), e.get("settlementPeriod"),
                                    e.get("price"), e.get("volume"), e.get("dataProvider")])
            except Exception as ex:
                log["errors"].append(f"price {tag}: {ex}")
    def write(name, header, rows):
        with gzip.open(out / name, "wt", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(header); w.writerows(rows)
    write("north_east_england_intensity_mix.csv.gz", ["from_utc", "to_utc", "forecast_gco2_kwh", "index"] + [f"{k}_pct" for k in FUELS], reg_rows)
    write("gb_national_intensity.csv.gz", ["from_utc", "to_utc", "forecast_gco2_kwh", "actual_gco2_kwh"], nat_rows)
    if not a.skip_prices:
        write("gb_market_index_price.csv.gz", ["start_utc", "settlement_date", "settlement_period", "price_gbp_mwh", "volume_mwh", "provider"], px_rows)
    log.update(rows={"regional": len(reg_rows), "national": len(nat_rows), "price": len(px_rows)})
    (out / "provenance.json").write_text(json.dumps(log, indent=2))
    archive = out.parent / f"Digital_Gardens_UK_GRID_{first}_{last}_DATA.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in out.iterdir():
            if f.is_file():
                z.write(f, f"{out.name}/{f.name}")
    print(f"\nRows: {log['rows']}  errors: {len(log['errors'])}")
    print(f"ZIP TO UPLOAD: {archive}")
    return 0


FUELS = ["biomass", "coal", "imports", "gas", "nuclear", "other", "hydro", "solar", "wind"]

if __name__ == "__main__":
    sys.exit(main())
