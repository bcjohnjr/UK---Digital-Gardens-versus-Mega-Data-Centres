"""Readers for the ERA5 weather and GB grid archives produced by the two downloaders in DATA/.

All series are returned as arrays of shape (n_years, 8760) in UTC, with 29 February removed so that every year has
8,760 hours. Gaps in the half-hourly grid record are filled by linear interpolation and the filled share is reported.
"""
import gzip, json, csv, re
import numpy as np, pandas as pd
from params import WX_DIR, GRID_DIR, WEATHER_YEARS, GRID_YEARS


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _year_matrix(times, values, years):
    s = pd.Series(np.asarray(values, float), index=pd.DatetimeIndex(times))
    s = s[~((s.index.month == 2) & (s.index.day == 29))]
    out = np.full((len(years), 8760), np.nan)
    for i, y in enumerate(years):
        v = s[s.index.year == y]
        if len(v):
            idx = pd.date_range(f"{y}-01-01", f"{y}-12-31 23:00", freq="h")
            idx = idx[~((idx.month == 2) & (idx.day == 29))]
            v = v.reindex(idx)
            out[i] = v.to_numpy()
    return out


def load_site(site, cols=("wind_speed_100m", "shortwave_radiation", "temperature_2m"), years=WEATHER_YEARS):
    f = WX_DIR / f"{slug(site)}_hourly_era5.csv.gz"
    df = pd.read_csv(f, usecols=["time_utc", "era5_grid_latitude", "era5_grid_longitude", *cols])
    t = pd.to_datetime(df.time_utc)
    res = {c: _year_matrix(t, df[c], years) for c in cols}
    res["grid_cell"] = (float(df.era5_grid_latitude.iloc[0]), float(df.era5_grid_longitude.iloc[0]))
    return res


def _half_hour_to_hourly(times, values, years):
    s = pd.Series(pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(float), index=pd.DatetimeIndex(times, tz=None))
    s = s[~s.index.duplicated()].sort_index()
    full = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31 23:30", freq="30min")
    s = s.reindex(full)
    filled = float(s.isna().mean())
    s = s.interpolate(limit_direction="both")
    h = s.resample("h").mean()
    return _year_matrix(h.index, h.to_numpy(), years), filled


def load_grid(years=GRID_YEARS):
    """Regional (North East England) forecast intensity, national actual intensity, regional mix and wholesale price."""
    out = {}
    reg = pd.read_csv(GRID_DIR / "north_east_england_intensity_mix.csv.gz")
    t = pd.to_datetime(reg.from_utc, utc=True).dt.tz_localize(None)
    out["ne_intensity"], out["ne_filled"] = _half_hour_to_hourly(t, reg.forecast_gco2_kwh, years)
    for fuel in ("gas", "nuclear", "wind", "solar", "imports", "biomass", "coal", "hydro", "other"):
        col = f"{fuel}_pct"
        if col in reg:
            out[f"ne_mix_{fuel}"], _ = _half_hour_to_hourly(t, reg[col], years)
    nat = pd.read_csv(GRID_DIR / "gb_national_intensity.csv.gz")
    t = pd.to_datetime(nat.from_utc, utc=True).dt.tz_localize(None)
    act = nat.actual_gco2_kwh.where(nat.actual_gco2_kwh.notna(), nat.forecast_gco2_kwh)
    out["gb_intensity"], out["gb_filled"] = _half_hour_to_hourly(t, act, years)
    pf = GRID_DIR / "gb_market_index_price.csv.gz"
    if pf.exists():
        px = pd.read_csv(pf)
        px = px[px.provider.astype(str).str.upper().str.contains("APX")] if "provider" in px else px
        px = px[pd.to_numeric(px.volume_mwh, errors="coerce").fillna(0) > 0]
        t = pd.to_datetime(px.start_utc, utc=True).dt.tz_localize(None)
        out["price"], out["price_filled"] = _half_hour_to_hourly(t, px.price_gbp_mwh, years)
    return out


def load_communities():
    from params import DATA
    rows = list(csv.DictReader(open(DATA / "communities.csv", newline="")))
    return {slug(r["community"]): dict(population=int(float(r["population_2021"])), it_mw=float(r["it_mw"]),
                                       lat=float(r["latitude"]), lon=float(r["longitude"]), river=r["main_river"]) for r in rows}
