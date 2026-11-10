#!/usr/bin/env python3
"""Hourly 24/7 fossil-free supply for Digital Gardens North Tyne, and grid supply for the comparator campuses.

Wind (four Northumberland upland/coastal proxies) and solar (mean of the eight host nodes) come from ERA5 2010-2025.
Digital Gardens buys the output of contracted wind and solar at CfD AR7 strike prices and serves its load hour by hour
in this order: wind and solar, battery, a renewable-fuel combined-cycle block, and only then the public grid. The block
burns HVO; when its tank falls to one third it switches to a tri-mix of HVO, biodiesel (B100) and biogas from the local
digesters. The hourly fossil-free score is the share of consumption not imported from the grid. Surplus renewable output
is sold at the hourly wholesale price (curtailed when the price is negative). Costs and grid emissions use 2018-2025,
the years with half-hourly prices and carbon intensity; the physical score is replayed over all sixteen weather years.
"""
import json, itertools
import numpy as np
import params as P
from data_io import load_site, load_grid, load_communities

OUT = P.OUT
B = P.BACKUP


# ----------------------------------------------------------------------------- resource
def power_curve(v):
    c = P.POWER
    # Illustrative 4-5 MW turbine curve replaces the inappropriate CUBED
    # normalised ramp. These are screening anchors, NOT a digitised
    # manufacturer-tested curve nor site-specific production verification.
    # 12% aggregate wake/availability/electrical losses are applied below.
    speeds = np.asarray([0, 2.99, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 20, 24.99, 25, 35])
    fractions = np.asarray([0, 0, 0, .025, .08, .20, .34, .48, .70, .90, .98, 1., 1., 1., 1., 0, 0])
    x = np.interp(np.asarray(v, dtype=float), speeds, fractions)
    return np.where((v < c["cut_in"]) | (v >= c["cut_out"]), 0.0,
                    x * c.get("wind_losses_factor", 0.88))


_SPEEDS = None


def wind_fleet(target_cf=None):
    """Fleet capacity factor (years x 8760), the raw ERA5 value and the speed scale needed to reach target_cf."""
    global _SPEEDS
    if _SPEEDS is None:
        _SPEEDS = np.stack([load_site(s, cols=("wind_speed_100m",))["wind_speed_100m"] for s in P.WIND_SITES])
    speeds = _SPEEDS
    raw = power_curve(speeds).mean(axis=0)
    if target_cf is None:
        return raw, float(raw.mean()), 1.0
    lo, hi = 0.3, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        cf = power_curve(speeds * k).mean()
        lo, hi = (k, hi) if cf < target_cf else (lo, k)
    k = (lo + hi) / 2
    return power_curve(speeds * k).mean(axis=0), float(raw.mean()), k


def sun_position(lat, lon, years):
    """Cosine of zenith, and sun azimuth/elevation unit vectors, at the middle of each preceding hour (UTC), 8760 per year.
    NOAA low-precision algorithm (declination, equation of time, hour angle)."""
    import pandas as pd
    out = []
    for y in years:
        idx = pd.date_range(f"{y}-01-01", f"{y}-12-31 23:00", freq="h")
        idx = idx[~((idx.month == 2) & (idx.day == 29))] - pd.Timedelta(minutes=30)
        doy = idx.dayofyear.to_numpy(); hr = idx.hour.to_numpy() + idx.minute.to_numpy() / 60
        g = 2 * np.pi / 365 * (doy - 1 + (hr - 12) / 24)
        eot = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
        dec = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
               - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
        tst = hr * 60 + eot + 4 * lon
        ha = np.radians(tst / 4 - 180)
        la = np.radians(lat)
        cz = np.sin(la) * np.sin(dec) + np.cos(la) * np.cos(dec) * np.cos(ha)
        out.append((cz, dec, ha))
    return out


def pv_fleet(tilt=35.0):
    """Plane-of-array capacity factor (south-facing, 35 degree tilt; isotropic diffuse; albedo 0.2) from ERA5 GHI and DNI,
    averaged over the eight host nodes."""
    c = P.POWER; comm = load_communities(); cfs = []
    b = np.radians(tilt)
    for n in P.NODES:
        d = load_site(P.NODE_LABEL[n], cols=("shortwave_radiation", "direct_normal_irradiance", "temperature_2m"))
        lat, lon = comm[n]["lat"], comm[n]["lon"]
        sp = sun_position(lat, lon, P.WEATHER_YEARS)
        cz = np.stack([s[0] for s in sp]); dec = np.stack([s[1] for s in sp]); ha = np.stack([s[2] for s in sp])
        la = np.radians(lat)
        # incidence on a south-facing plane tilted by b (equivalent latitude la - b)
        ci = np.sin(la - b) * np.sin(dec) + np.cos(la - b) * np.cos(dec) * np.cos(ha)
        ghi = d["shortwave_radiation"]; dni = d["direct_normal_irradiance"]
        up = cz > 0.02
        beam_h = np.where(up, dni * cz, 0.0)
        dhi = np.clip(ghi - beam_h, 0, None)
        poa = np.where(up, dni * np.clip(ci, 0, None), 0.0) + dhi * (1 + np.cos(b)) / 2 + ghi * 0.2 * (1 - np.cos(b)) / 2
        cell = d["temperature_2m"] + c["pv_noct_rise"] * poa / 800.0
        cfs.append(np.clip(poa / 1000.0 * c["pv_performance_ratio"] * (1 + c["pv_temp_coeff"] * (cell - 25.0)), 0, 1))
    return np.mean(cfs, axis=0)


# ----------------------------------------------------------------------------- load, vehicles, biogas
def households():
    comm = load_communities()
    pop = sum(v["population"] for v in comm.values())
    return pop, pop / P.HEAT["persons_per_household"]


def vehicles():
    M = P.MOBILITY; pop, hh = households(); d = M["car_dist"]
    existing = hh * (d[1] * 1 + d[2] * 2 + d[3] * M["three_plus_mean"])
    new = hh * d[0]
    total = existing + new
    phev = total * M["phev_share"]; bev = total - phev
    ekm = M["km_per_ev"] * (bev + phev * M["phev_electric_share"])
    return dict(households=hh, existing=existing, new_for_zero_car=new, total=total, bev=bev, phev=phev,
                charging_gwh=ekm * M["kwh_per_100km"] / 100 / 1e6)


def biogas_mwh_per_year():
    LV = P.LIVESTOCK; cs = LV["catchment_share"]
    ch4 = (LV["ne_dairy"] * cs * LV["biogas_m3_ch4"]["dairy"] + LV["ne_beef"] * cs * LV["biogas_m3_ch4"]["beef"]
           + LV["food_waste_t"] * LV["food_waste_m3_ch4_t"])
    return ch4 * LV["ch4_mj_m3"] / 3600


def community_electricity_mw():
    pop, hh = households()
    F = P.FOOD
    veg_t = pop * F["veg_kg_per_resident"] / 1000; sea_t = pop * F["seafood_kg_live_per_resident"] / 1000
    ha = veg_t / (F["greenhouse_kg_m2"] * 10)
    v = vehicles()
    gwh = (ha * F["greenhouse_el_mwh_per_ha"] + sea_t * F["ras_el_mwh_per_t"]) / 1000 + v["charging_gwh"] + F["processing_el_gwh"] + F["seaweed_el_gwh"] + F["home_hp_el_gwh"] + F["seaweed_pumping_el_gwh"]
    return gwh * 1000 / 8760, dict(population=pop, households=hh, greenhouse_ha=ha, veg_t=veg_t, seafood_t=sea_t, vehicles=v, community_gwh=gwh)


def dg_load_mw():
    n = P.NETWORK
    it = n["it_mw"] * n["it_utilisation"]
    comm, info = community_electricity_mw()
    return it * n["pue"] + comm, it, comm, info


# ----------------------------------------------------------------------------- dispatch (vectorised over portfolios, accumulated)
L_PER_MWH = 3600.0 / (B["efficiency"] * B["hvo_lhv_mj_l"])


def dispatch_year(wc, pc, load, W, S, E, Pw, A_l, prices, intens, biogas_mwh_yr, strike=None, gate=None, gate_g=None, record=None, export_cap=None):
    """One year. A_l: annual liquid-fuel allowance (litres) per portfolio. prices: dict name->(8760,), intens: dict name->(8760,).
    Returns accumulated annual totals per portfolio."""
    eta = np.sqrt(P.POWER["battery_rt"])
    n = len(W)
    soc = 0.5 * E.copy()
    has_bk = A_l > 0
    bk_mw = np.where(has_bk, B["mw"], 0.0)
    tank_cap = np.minimum(B["tank_days"] * 24 * B["mw"] * L_PER_MWH, A_l)
    tank = tank_cap.copy()
    deliver = np.maximum(A_l - tank_cap, 0.0) / 8760.0     # tank starts full and is refilled at year end: draw <= allowance
    bg_rate = biogas_mwh_yr / 8760.0                     # MWh of biogas energy produced per hour
    bg_cap = B["biogas_buffer_days"] * 24 * bg_rate
    bg = np.full(n, bg_cap)
    acc = {k: np.zeros(n) for k in ("imp", "exp", "cur", "bk_mwh", "hvo_l", "b100_l", "biogas_mwh", "bg_vented")}
    for k in prices:
        acc[f"impcost_{k}"] = np.zeros(n); acc[f"expval_{k}"] = np.zeros(n); acc[f"expcap_{k}"] = np.zeros(n)
    for k in intens:
        acc[f"impt_{k}"] = np.zeros(n)
    neg = prices["hist"] < 0
    for t in range(len(wc)):
        g = W * wc[t] + S * pc[t]
        net = g - load
        pos = net >= 0
        c = np.minimum(np.minimum(np.where(pos, net, 0.0), Pw), np.maximum(E - soc, 0) / eta)
        d = np.minimum(np.minimum(np.where(pos, 0.0, -net), Pw), soc * eta)
        soc = soc + c * eta - d / eta
        surplus = np.where(pos, net - c, 0.0)
        deficit = np.where(pos, 0.0, -net - d)
        # renewable-fuel block
        tank = np.minimum(tank + deliver, tank_cap)
        trimix = tank < B["trimix_trigger"] * tank_cap
        fuel_mwh_needed_per_mwh = 3.6 / B["efficiency"] / 3.6             # MWh fuel per MWh_e
        gen_bk = np.minimum(deficit, bk_mw)
        if gate is not None and gate[t] <= gate_g:
            gen_bk = gen_bk * 0.0                      # carbon-aware: import when the grid is cleaner than the fuel
        fuel_e = gen_bk * fuel_mwh_needed_per_mwh                          # MWh of fuel energy
        bg_use = np.where(trimix, np.minimum(fuel_e * B["trimix_biogas_max_share"], bg), 0.0)
        liq_e = fuel_e - bg_use
        liq_l = liq_e * 3600 / B["hvo_lhv_mj_l"]
        short = liq_l > tank
        scale = np.where(short, np.where(liq_l > 0, tank / np.maximum(liq_l, 1e-12), 0.0), 1.0)
        gen_bk = np.where(short, (bg_use + liq_e * scale) / fuel_mwh_needed_per_mwh, gen_bk)
        liq_l = liq_l * scale
        tank = tank - liq_l
        bg = np.minimum(bg - bg_use + bg_rate, bg_cap)
        b100 = np.where(trimix, liq_l * B["trimix_b100_share_of_liquid"], 0.0)
        imp = deficit - gen_bk
        acc["imp"] += imp; acc["bk_mwh"] += gen_bk
        if record is not None:
            for k_, v_ in (("wind", W * wc[t]), ("solar", S * pc[t]), ("charge", c), ("discharge", d), ("block", gen_bk), ("import", imp),
                           ("surplus", surplus), ("tank", tank), ("trimix", trimix.astype(float))):
                record.setdefault(k_, []).append(float(v_[0]))
        acc["hvo_l"] += liq_l - b100; acc["b100_l"] += b100; acc["biogas_mwh"] += bg_use
        if export_cap is not None:
            over = np.maximum(surplus - export_cap, 0.0); acc["cur"] += over; surplus = surplus - over
        if neg[t]:
            acc["cur"] += surplus
        else:
            acc["exp"] += surplus
            for k, p in prices.items():
                acc[f"expval_{k}"] += surplus * max(p[t], 0.0)
                if strike is not None:
                    acc[f"expcap_{k}"] += surplus * np.minimum(max(p[t], 0.0), strike)
        for k, p in prices.items():
            acc[f"impcost_{k}"] += imp * p[t]
        for k, ci in intens.items():
            acc[f"impt_{k}"] += imp * ci[t] / 1000.0
    return acc


def crf(r, n):
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def non_commodity():
    return sum(P.COSTS["non_commodity_gbp_mwh"].values())


def annual_fixed(E, A_l):
    C = P.COSTS
    batt = E * 1000 * C["battery_capex_gbp_kwh"] * (crf(C["discount_rate"], C["battery_life"]) + C["battery_fom_frac"])
    has = A_l > 0
    tank_m3 = np.minimum(B["tank_days"] * 24 * B["mw"] * L_PER_MWH, A_l) / 1000
    bk = np.where(has, B["mw"] * 1000 * (B["capex_gbp_kw"] * crf(C["discount_rate"], C["finance_years"]) + B["fom_gbp_kw_yr"]), 0.0)
    tank = tank_m3 * B["tank_gbp_m3"] * crf(C["discount_rate"], C["finance_years"]) + tank_m3 * 1000 * B["hvo_gbp_l"] * B["carry_rate"]
    return batt, bk, tank


def evaluate(W, S, E, Pw, A_l, wind, pv, grid, load, years_idx, biogas_mwh_yr):
    C = P.COSTS; L = P.LCA
    n = len(W); ny = len(years_idx)
    r = {}
    def put(k, j, v):
        r.setdefault(k, np.zeros((n, ny)))[:, j] = v
    batt, bk, tank = annual_fixed(E, A_l)
    for j, yi in enumerate(years_idx):
        wc, pc = wind[yi], pv[yi]
        gi = yi - (len(wind) - len(grid["gb_intensity"]))
        prices = dict(hist=grid["price"][gi], norm=grid["price_norm"][gi])
        intens = dict(gb=grid["gb_intensity"][gi], ne=grid["ne_intensity"][gi])
        wm = W * wc.sum(); sm = S * pc.sum()
        strike = np.where(wm + sm > 0, (wm * C["ppa_wind_gbp_mwh"] + sm * C["ppa_solar_gbp_mwh"]) / np.maximum(wm + sm, 1e-9), 0.0)
        a = dispatch_year(wc, pc, load, W, S, E, Pw, A_l, prices, intens, biogas_mwh_yr, strike)
        ppa = wm * C["ppa_wind_gbp_mwh"] + sm * C["ppa_solar_gbp_mwh"]
        fuel = a["hvo_l"] * B["hvo_gbp_l"] + a["b100_l"] * B["b100_gbp_l"]
        for k in ("hist", "norm"):
            base = ppa + a[f"impcost_{k}"] + batt + bk + tank + a["bk_mwh"] * B["vom_gbp_mwh"] + fuel
            put(f"cost_{k}", j, base - a[f"expcap_{k}"])           # central: surplus resold at no more than its contract price
            put(f"cost_full_{k}", j, base - a[f"expval_{k}"])      # surplus resold at the full hourly price
            put(f"cost_zero_{k}", j, base)                         # surplus earns nothing
            put(f"expval_{k}", j, a[f"expval_{k}"]); put(f"expcap_{k}", j, a[f"expcap_{k}"]); put(f"impcost_{k}", j, a[f"impcost_{k}"])
        put("ppa", j, ppa); put("fuel_cost", j, fuel); put("fixed", j, batt + bk + tank)
        lca_ren = (wm * L["wind_g_kwh"] + sm * L["solar_g_kwh"]) / 1000.0 + E * 1000 * L["battery_kg_per_kwh"] / L["battery_life"] / 1000.0
        lca_fuel = (a["hvo_l"] * B["hvo_lhv_mj_l"] * B["lca_g_mj"]["hvo"] + a["b100_l"] * B["b100_lhv_mj_l"] * B["lca_g_mj"]["b100"]
                    + a["biogas_mwh"] * 3600 * B["lca_g_mj"]["biogas"]) / 1e6
        gen_tot = np.maximum(wm + sm, 1e-9)
        cons_share = np.clip((gen_tot - a["exp"]) / gen_tot, 0, 1)            # exported output carries its own footprint
        put("lca_t", j, lca_ren * cons_share + lca_fuel); put("lca_all_output_t", j, lca_ren + lca_fuel); put("lca_fuel_t", j, lca_fuel)
        bio_co2 = (a["hvo_l"] * 0.78 * 0.848 + a["b100_l"] * 0.88 * 0.77) * 44 / 12 / 1000 + a["biogas_mwh"] * 3.6 * 0.0561
        put("biogenic_t", j, bio_co2)
        for k in ("imp", "exp", "cur", "bk_mwh", "hvo_l", "b100_l", "biogas_mwh", "impt_gb", "impt_ne"):
            put(k, j, a[k])
        put("wind_mwh", j, wm); put("solar_mwh", j, sm)
        put("cfe", j, 1 - a["imp"] / (load * 8760))
    return r


def physics(W, S, E, Pw, A_l, wind, pv, load, biogas):
    """Fossil-free score and fuel use of each portfolio in each of the 16 weather years (no prices needed)."""
    z = np.zeros(8760)
    cfe = np.zeros((len(W), len(wind))); fuel = np.zeros_like(cfe); bkm = np.zeros_like(cfe)
    for yi in range(len(wind)):
        a = dispatch_year(wind[yi], pv[yi], load, W, S, E, Pw, A_l, dict(hist=z), dict(gb=z), biogas)
        cfe[:, yi] = 1 - a["imp"] / (load * 8760); fuel[:, yi] = (a["hvo_l"] + a["b100_l"]) / 1e6; bkm[:, yi] = a["bk_mwh"] / 1e3
    return cfe, fuel, bkm


def comparator_year(load_mw, grid, gi, price_key="price", rego=True):
    price = grid[price_key][gi]
    mwh = load_mw * 8760
    energy = load_mw * price.sum() + (P.COSTS["rego_gbp_mwh"] * mwh if rego else 0.0)
    return dict(mwh=mwh, energy_cost_gbp=energy, energy_gbp_mwh=energy / mwh,
                gb_t=load_mw * grid["gb_intensity"][gi].sum() / 1000.0, ne_t=load_mw * grid["ne_intensity"][gi].sum() / 1000.0,
                gb_g_kwh=float(grid["gb_intensity"][gi].mean()), ne_g_kwh=float(grid["ne_intensity"][gi].mean()))


def pick(r, idx):
    return {k: float(v[idx].mean()) for k, v in r.items()}


def main():
    OUT.mkdir(exist_ok=True)
    grid = load_grid()
    load, it, comm, info = dg_load_mw()
    biogas = biogas_mwh_per_year()
    wind, raw_cf, k = wind_fleet(P.POWER["wind_cf_central"])
    pv = pv_fleet()
    gy = [P.WEATHER_YEARS.index(y) for y in P.GRID_YEARS]
    m25 = float(np.nanmean(grid["price"][-1]))
    grid["price_norm"] = grid["price"] / np.nanmean(grid["price"], axis=1, keepdims=True) * m25
    for key in ("price", "price_norm", "gb_intensity", "ne_intensity"):
        grid[key] = np.nan_to_num(grid[key], nan=float(np.nanmean(grid[key])))

    Wg = np.arange(0, 1001, 50.0); Sg = np.arange(0, 801, 100.0); Eg = np.array([0, 100, 200, 400, 800.0])
    Ag = np.array(B["allowance_ml"]) * 1e6
    pf = np.array(list(itertools.product(Wg, Sg, Eg, Ag)))
    W, S, E, A = pf.T; Pw = E / P.POWER["battery_hours"]
    r = evaluate(W, S, E, Pw, A, wind, pv, grid, load, gy, biogas)
    mwh = load * 8760
    cost = r["cost_norm"].mean(1) / mwh; cost_h = r["cost_hist"].mean(1) / mwh
    cfe = r["cfe"].mean(1); cfe_min = r["cfe"].min(1)
    # website portfolio, with and without the renewable-fuel block
    web_pf = np.array([[267.167, 89.056, 250.0, 100.0, a] for a in Ag])
    rw = evaluate(*web_pf.T, wind, pv, grid, load, gy, biogas)
    comp = {}
    for case in ("price", "price_norm"):
        ys = [comparator_year(load, grid, gi, case) for gi in range(len(P.GRID_YEARS))]
        comp[case] = {k: float(np.mean([y[k] for y in ys])) for k in ys[0]}
    targets = [0.80, 0.90, 0.95, 0.98, 0.99, 0.995, 1.0]
    gen = (r["wind_mwh"] + r["solar_mwh"]).mean(1)
    within = gen <= P.COSTS["procurement_limit"] * mwh
    unconstrained = []
    for tgt in targets:
        ok = (cfe >= tgt - 1e-12) & (cfe_min >= min(tgt, 0.999) - 0.02)
        if ok.any():
            i = int(np.argmin(np.where(ok, cost, np.inf)))
            unconstrained.append(dict(target=tgt, wind_mw=W[i], solar_mwp=S[i], battery_mwh=E[i], allowance_ml=A[i] / 1e6, cfe_mean=cfe[i],
                                      cost_gbp_mwh=cost[i], gen_ratio=gen[i] / mwh, export_gwh=r["exp"][i].mean() / 1e3))
    frontier = []
    for tgt in targets:
        ok = (cfe >= tgt - 1e-12) & (cfe_min >= min(tgt, 0.999) - 0.02) & within
        if not ok.any():
            continue
        i = int(np.argmin(np.where(ok, cost, np.inf)))
        f = dict(target=tgt, idx=i, gen_ratio=gen[i] / mwh, wind_mw=W[i], solar_mwp=S[i], battery_mwh=E[i], allowance_ml=A[i] / 1e6, cfe_mean=cfe[i], cfe_min_year=cfe_min[i],
                 cost_gbp_mwh=cost[i], cost_hist_gbp_mwh=cost_h[i])
        f.update({f"mean_{k}": v for k, v in pick(r, i).items()})
        frontier.append(f)
    # cheapest with no backup, for each target (the battery-only route)
    no_bk = []
    for tgt in targets:
        ok = (cfe >= tgt - 1e-12) & (A == 0) & within
        if ok.any():
            i = int(np.argmin(np.where(ok, cost, np.inf)))
            no_bk.append(dict(target=tgt, wind_mw=W[i], solar_mwp=S[i], battery_mwh=E[i], cfe_mean=cfe[i], cost_gbp_mwh=cost[i]))
    web = []
    for j, a in enumerate(Ag):
        d = dict(allowance_ml=a / 1e6, cfe_mean=float(rw["cfe"][j].mean()), cfe_min=float(rw["cfe"][j].min()),
                 cost_gbp_mwh=float(rw["cost_norm"][j].mean() / mwh), cost_hist_gbp_mwh=float(rw["cost_hist"][j].mean() / mwh))
        d.update({f"mean_{k}": float(v[j].mean()) for k, v in rw.items()})
        web.append(d)
    # surplus valuation tests
    export_tests = {}
    for name in ("full", "zero"):
        c_f = r[f"cost_{name}_norm"].mean(1) / mwh
        rows = []
        for tgt in targets:
            ok = (cfe >= tgt - 1e-12) & (cfe_min >= min(tgt, 0.999) - 0.02) & within
            if ok.any():
                i = int(np.argmin(np.where(ok, c_f, np.inf)))
                rows.append(dict(target=tgt, wind_mw=W[i], solar_mwp=S[i], battery_mwh=E[i], allowance_ml=A[i] / 1e6, cfe_mean=cfe[i],
                                 cost_gbp_mwh=c_f[i], export_gwh=r["exp"][i].mean() / 1e3))
        export_tests[name] = rows
    # 16-year replay and wind-yield sensitivity for the frontier and website (+ largest allowance) portfolios
    sel = np.array([[f["wind_mw"], f["solar_mwp"], f["battery_mwh"], f["battery_mwh"] / P.POWER["battery_hours"], f["allowance_ml"] * 1e6] for f in frontier]
                   + [[267.167, 89.056, 250.0, 100.0, 0.0], [267.167, 89.056, 250.0, 100.0, Ag.max()]])
    labels = [f"CFE>={f['target']}" for f in frontier] + ["website, grid backup", f"website + {Ag.max()/1e6:.0f} ML block"]
    ph_cfe, ph_fuel, ph_bk = physics(*sel.T, wind, pv, load, biogas)
    wind_tests = {}
    for cf in P.POWER["wind_cf_tests"] + ["raw"]:
        wcf, _, kk = wind_fleet(None if cf == "raw" else cf)
        c2, f2, _ = physics(*sel.T, wcf, pv, load, biogas)
        wind_tests[str(cf)] = dict(scale=kk, fleet_cf=float(wcf.mean()), cfe_mean=c2.mean(1).tolist(), cfe_min=c2.min(1).tolist(),
                                   fuel_ml_mean=f2.mean(1).tolist(), fuel_ml_max=f2.max(1).tolist())
    out = dict(
        load_mw=load, it_mw_avg=it, community_mw=comm, community_info=info, annual_load_gwh=load * 8.76, biogas_mwh_yr=biogas,
        backup=dict(B, l_per_mwh=L_PER_MWH),
        wind=dict(raw_era5_fleet_cf=raw_cf, scale_to_central=k, central_cf=P.POWER["wind_cf_central"]),
        pv_cf=float(pv.mean()),
        wholesale_mean_by_year={str(y): float(np.mean(grid["price"][i])) for i, y in enumerate(P.GRID_YEARS)},
        gb_intensity_mean_by_year={str(y): float(np.mean(grid["gb_intensity"][i])) for i, y in enumerate(P.GRID_YEARS)},
        ne_intensity_mean_by_year={str(y): float(np.mean(grid["ne_intensity"][i])) for i, y in enumerate(P.GRID_YEARS)},
        ne_filled_share=grid["ne_filled"], gb_filled_share=grid["gb_filled"], price_filled_share=grid.get("price_filled"), price_2025_mean=m25,
        non_commodity_gbp_mwh=non_commodity(), comparator_at_dg_load=comp, frontier=frontier, unconstrained_frontier=unconstrained, no_backup_frontier=no_bk,
        website_portfolio=web, export_value_tests=export_tests,
        sixteen_year=dict(portfolios=labels, cfe_mean=ph_cfe.mean(1).tolist(), cfe_min=ph_cfe.min(1).tolist(),
                          fuel_ml_mean=ph_fuel.mean(1).tolist(), fuel_ml_max=ph_fuel.max(1).tolist(), backup_gwh_mean=ph_bk.mean(1).tolist(),
                          cfe_by_year=ph_cfe.tolist(), fuel_by_year=ph_fuel.tolist()),
        wind_tests=wind_tests,
        search=dict(n_portfolios=len(W), wind_mw=Wg.tolist(), solar_mwp=Sg.tolist(), battery_mwh=Eg.tolist(), allowance_ml=B["allowance_ml"]),
    )
    json.dump(out, open(OUT / "power_247.json", "w"), indent=2, default=float)
    np.savez_compressed(OUT / "power_247_grid.npz", W=W, S=S, E=E, A=A, cost=cost, cost_hist=cost_h, cfe=cfe, cfe_min=cfe_min,
                        impt_gb=r["impt_gb"].mean(1), lca_t=r["lca_t"].mean(1), fuel_l=(r["hvo_l"] + r["b100_l"]).mean(1),
                        exp=r["exp"].mean(1), gen=(r["wind_mwh"] + r["solar_mwh"]).mean(1), cost_full=r["cost_full_norm"].mean(1) / mwh,
                        cost_zero=r["cost_zero_norm"].mean(1) / mwh, fuel_max=(r["hvo_l"] + r["b100_l"]).max(1))
    print(json.dumps({k: out[k] for k in ("annual_load_gwh", "community_mw", "biogas_mwh_yr", "wind", "pv_cf", "wholesale_mean_by_year",
                                          "gb_intensity_mean_by_year", "comparator_at_dg_load")}, indent=1, default=float))
    for f in frontier:
        print({k: round(f[k], 3) for k in ("target", "wind_mw", "solar_mwp", "battery_mwh", "allowance_ml", "cfe_mean", "cfe_min_year", "cost_gbp_mwh",
                                            "mean_imp", "mean_exp", "mean_bk_mwh", "mean_hvo_l", "mean_b100_l", "mean_biogas_mwh", "mean_impt_gb", "mean_lca_t")})
    print("no backup", [(f["target"], f["wind_mw"], f["solar_mwp"], f["battery_mwh"], round(f["cost_gbp_mwh"], 1)) for f in no_bk])
    for w in web:
        print("website", {k: round(w[k], 3) for k in ("allowance_ml", "cfe_mean", "cost_gbp_mwh", "mean_imp", "mean_bk_mwh")})
    print("16y", json.dumps({k: out["sixteen_year"][k] for k in ("portfolios", "cfe_mean", "cfe_min", "fuel_ml_max")}, default=float))
    print("wind tests", json.dumps({k: (round(v["scale"], 3), [round(x, 3) for x in v["cfe_mean"]]) for k, v in wind_tests.items()}))


if __name__ == "__main__" and len(__import__("sys").argv) == 1:
    main()


# ============================================================================= design case: renewables -> battery -> grid -> block (grid failure only)
def outage_autonomy(port, wind, pv, load, biogas, max_days=30):
    """Hours of full-load supply during a complete grid outage starting at the worst hour (largest 14-day renewable deficit)
    of each weather year: wind+solar, battery, then the block on its 14-day HVO tank with the one-third tri-mix switch."""
    W, S, E = port
    res = []
    eta = np.sqrt(P.POWER["battery_rt"])
    tank_cap = B["tank_days"] * 24 * B["mw"] * L_PER_MWH
    bg_rate = biogas / 8760.0; bg_cap = B["biogas_buffer_days"] * 24 * bg_rate
    for yi in range(len(wind)):
        g = W * wind[yi] + S * pv[yi]
        deficit = np.convolve(np.maximum(load - g, 0), np.ones(336), "valid")
        t0 = int(np.argmax(deficit))
        gg = np.concatenate([g, W * wind[(yi + 1) % len(wind)] + S * pv[(yi + 1) % len(wind)]])[t0:t0 + max_days * 24]
        soc = 0.5 * E; tank = tank_cap; bg = bg_cap; hours = 0; trimix_h = 0
        for h in range(len(gg)):
            net = gg[h] - load
            if net >= 0:
                soc = min(E, soc + min(net, E / 4) * eta)
            else:
                d = min(-net, E / 4, soc * eta); soc -= d / eta; need = -net - d
                need = min(need, B["mw"]) if need <= B["mw"] else None
                if need is None:
                    break
                fuel_e = need / B["efficiency"]
                use_bg = 0.0
                if tank < B["trimix_trigger"] * tank_cap:
                    use_bg = min(fuel_e * B["trimix_biogas_max_share"], bg); trimix_h += 1
                liq = (fuel_e - use_bg) * 3600 / B["hvo_lhv_mj_l"]
                if liq > tank:
                    break
                tank -= liq; bg = min(bg - use_bg + bg_rate, bg_cap)
            hours += 1
        res.append(dict(year=P.WEATHER_YEARS[yi], hours=hours, trimix_hours=trimix_h))
    return res


def design_main():
    """Search for the design case and write OUTPUT/design.json."""
    grid = load_grid()
    load, it, comm, info = dg_load_mw()
    biogas = biogas_mwh_per_year()
    wind, raw_cf, k = wind_fleet(P.POWER["wind_cf_central"]); pv = pv_fleet()
    gy = [P.WEATHER_YEARS.index(y) for y in P.GRID_YEARS]
    m25 = float(np.nanmean(grid["price"][-1]))
    grid["price_norm"] = grid["price"] / np.nanmean(grid["price"], axis=1, keepdims=True) * m25
    for key in ("price", "price_norm", "gb_intensity", "ne_intensity"):
        grid[key] = np.nan_to_num(grid[key], nan=float(np.nanmean(grid[key])))
    Wg = np.arange(0, 1201, 50.0); Sg = np.arange(0, 1201, 100.0); Eg = np.array([0, 100, 200, 300, 400.0])
    pf = np.array(list(itertools.product(Wg, Sg, Eg)))
    W, S, E = pf.T; Pw = E / P.POWER["battery_hours"]; A0 = np.zeros(len(W))
    r = evaluate(W, S, E, Pw, A0, wind, pv, grid, load, gy, biogas)
    mwh = load * 8760
    C = P.COSTS
    # standby block: capital, fixed O&M, 14-day tank and inventory, monthly test runs on HVO
    tank_l = B["tank_days"] * 24 * B["mw"] * L_PER_MWH
    test_mwh = B["test_hours_per_year"] * B["mw"]
    standby = (B["mw"] * 1000 * (B["capex_gbp_kw"] * crf(C["discount_rate"], C["finance_years"]) + B["fom_gbp_kw_yr"])
               + tank_l / 1000 * B["tank_gbp_m3"] * crf(C["discount_rate"], C["finance_years"]) + tank_l * B["hvo_gbp_l"] * B["carry_rate"]
               + test_mwh * (B["vom_gbp_mwh"] + L_PER_MWH * B["hvo_gbp_l"])
               + (sum(km for _, _, km in P.ISLAND["routes"]) * P.ISLAND["circuits"] * B["island_network_gbp_km"] + B["island_switchgear_gbp"])
               * (crf(C["discount_rate"], 40) + 0.01))
    test_t = test_mwh * L_PER_MWH * B["hvo_lhv_mj_l"] * B["lca_g_mj"]["hvo"] / 1e6
    cost = {"full": (r["cost_full_norm"].mean(1) + standby) / mwh, "capped": (r["cost_norm"].mean(1) + standby) / mwh,
            "zero": (r["cost_zero_norm"].mean(1) + standby) / mwh}
    cost_hist = (r["cost_full_hist"].mean(1) + standby) / mwh
    cfe = r["cfe"].mean(1); cfe_min = r["cfe"].min(1)
    gen = (r["wind_mwh"] + r["solar_mwh"]).mean(1)
    ok_batt = (E <= C["battery_max_mwh"]) & (gen <= C["sellback_limit"] * mwh)
    def pick_at(tgt, credit="full"):
        ok = ok_batt & (cfe >= tgt)
        return int(np.argmin(np.where(ok, cost[credit], np.inf))) if ok.any() else None
    rows = []
    for tgt in (0.5, 0.6, 0.65, 0.7, 0.75, 0.8):
        i = pick_at(tgt)
        if i is None:
            continue
        rows.append(dict(target=tgt, wind_mw=W[i], solar_mwp=S[i], battery_mwh=E[i], self_supply=cfe[i], self_supply_min=cfe_min[i],
                         cost_full=cost["full"][i], cost_capped=cost["capped"][i], cost_zero=cost["zero"][i], cost_hist=cost_hist[i],
                         gen_ratio=gen[i] / mwh, import_gwh=r["imp"][i].mean() / 1e3, export_gwh=r["exp"][i].mean() / 1e3,
                         curtail_gwh=r["cur"][i].mean() / 1e3, import_t=r["impt_gb"][i].mean(), lca_t=r["lca_t"][i].mean() + test_t,
                         export_revenue=r["expval_norm"][i].mean(), import_cost=r["impcost_norm"][i].mean(), ppa=r["ppa"][i].mean()))
    sel = next(x for x in rows if abs(x["target"] - C["self_supply_target"]) < 1e-9)
    i = pick_at(C["self_supply_target"])
    port = (W[i], S[i], E[i])
    # sixteen-year and wind-yield replays of the design portfolio
    Wv, Sv, Ev = [np.array([v]) for v in port]
    def phys(wcf):
        out = []
        for yi in range(len(wcf)):
            a = dispatch_year(wcf[yi], pv[yi], load, Wv, Sv, Ev, Ev / 4, np.zeros(1), dict(hist=np.zeros(8760)), dict(gb=np.zeros(8760)), biogas)
            out.append(1 - a["imp"][0] / (load * 8760))
        return out
    p16 = phys(wind)
    wt = {}
    for cf in P.POWER["wind_cf_tests"] + ["raw"]:
        wcf, _, kk = wind_fleet(None if cf == "raw" else cf)
        v = phys(wcf); wt[str(cf)] = dict(scale=kk, fleet_cf=float(wcf.mean()), mean=float(np.mean(v)), min=float(np.min(v)))
    aut = outage_autonomy((0.0, 0.0, port[2]), wind, pv, load, biogas)          # islanded nodes: battery + block only
    aut_ren = outage_autonomy(port, wind, pv, load, biogas)                      # conditional: contracted renewables islanded too
    # re-optimisation with unscaled ERA5 winds
    wraw, _, _ = wind_fleet(None)
    rr = evaluate(W, S, E, Pw, A0, wraw, pv, grid, load, gy, biogas)
    cost_raw = (rr["cost_full_norm"].mean(1) + standby) / mwh; cfe_raw = rr["cfe"].mean(1)
    gen_raw = (rr["wind_mwh"] + rr["solar_mwh"]).mean(1)
    ok_raw = (E <= C["battery_max_mwh"]) & (gen_raw <= C["sellback_limit"] * mwh)
    j_sel = i
    raw = dict(selected_at_raw=dict(self_supply=float(cfe_raw[j_sel]), cost_full=float(cost_raw[j_sel])),
               max_self_supply=float(cfe_raw[ok_raw].max()))
    okt = ok_raw & (cfe_raw >= C["self_supply_target"])
    if okt.any():
        jr = int(np.argmin(np.where(okt, cost_raw, np.inf)))
        raw["reoptimised"] = dict(wind_mw=W[jr], solar_mwp=S[jr], battery_mwh=E[jr], self_supply=float(cfe_raw[jr]), cost_full=float(cost_raw[jr]),
                                  cost_capped=float((rr["cost_norm"][jr].mean() + standby) / mwh), cost_zero=float((rr["cost_zero_norm"][jr].mean() + standby) / mwh),
                                  export_gwh=float(rr["exp"][jr].mean() / 1e3), gen_ratio=float(gen_raw[jr] / mwh))
    else:
        jr = int(np.argmax(np.where(ok_raw, cfe_raw, -1)))
        raw["reoptimised"] = None
        raw["best_within_limits"] = dict(wind_mw=W[jr], solar_mwp=S[jr], battery_mwh=E[jr], self_supply=float(cfe_raw[jr]), cost_full=float(cost_raw[jr]))
    # unrestricted battery and output: cheapest portfolio reaching the target with raw winds
    okb = cfe_raw >= C["self_supply_target"]
    if okb.any():
        jb = int(np.argmin(np.where(okb, cost_raw, np.inf)))
        raw["reoptimised_unrestricted"] = dict(wind_mw=W[jb], solar_mwp=S[jb], battery_mwh=E[jb], self_supply=float(cfe_raw[jb]), cost_full=float(cost_raw[jb]),
                                               gen_ratio=float(gen_raw[jb] / mwh))
    sel["export_capture_gbp_mwh"] = sel["export_revenue"] / (sel["export_gwh"] * 1e3)
    sel["mean_price_gbp_mwh"] = m25
    # hourly record of a winter fortnight with a grid outage for the figure (design year 2021)
    out = dict(load_mw=load, annual_load_gwh=load * 8.76, community_mw=comm, community_info=info, standby_gbp=standby, test_t=test_t,
               tank_ml=tank_l / 1e6, test_mwh=test_mwh, frontier=rows, selected=sel, sixteen_year=dict(mean=float(np.mean(p16)), min=float(np.min(p16)), by_year=p16),
               wind_tests=wt, outage=aut, outage_with_renewables=aut_ren, raw_wind=raw, comparator=dict(energy_gbp_mwh=float(np.mean([comparator_year(load, grid, gi, "price_norm")["energy_gbp_mwh"] for gi in range(8)])),
                                                         energy_hist=float(np.mean([comparator_year(load, grid, gi, "price")["energy_gbp_mwh"] for gi in range(8)]))),
               search=dict(n=len(W), wind=Wg.tolist(), solar=Sg.tolist(), battery=Eg.tolist()))
    json.dump(out, open(OUT / "design.json", "w"), indent=2, default=float)
    np.savez_compressed(OUT / "design_grid.npz", W=W, S=S, E=E, cfe=cfe, cost_full=cost["full"], cost_capped=cost["capped"], cost_zero=cost["zero"], gen=gen)
    for x in rows:
        print({k: round(v, 3) for k, v in x.items()})
    print("selected", port, "16y", round(np.mean(p16), 3), round(np.min(p16), 3), "wind", {k: (round(v["mean"], 3)) for k, v in wt.items()})
    print("outage hours by year", [a["hours"] for a in aut], "trimix", [a["trimix_hours"] for a in aut])
    print("standby £m", standby / 1e6, "comparator", out["comparator"])


if __name__ == "__main__" and len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "design":
    design_main()
