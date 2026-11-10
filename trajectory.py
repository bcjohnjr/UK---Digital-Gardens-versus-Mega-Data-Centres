#!/usr/bin/env python3
"""25-year emissions and cost of the selected Digital Gardens portfolios against grid-supplied campuses on the GB
decarbonisation path, under two operating rules for the renewable-fuel block.

Fossil-free rule: the combined-cycle block runs before any grid import (hourly fossil-free supply).
Carbon-aware rule: the block runs only in hours when the GB grid is more carbon-intensive than the block's own
life-cycle intensity (HVO at 21.6 g CO2e/MJ and 52% efficiency, about 150 g/kWh); otherwise the grid is used.
The 2018-2025 hourly GB intensity shapes are rescaled to each year's annual mean on the path: observed 2025 mean,
Clean Power 2030 (<50 g/kWh), Climate Change Committee 10 g/kWh in 2035, held thereafter.
"""
import json
import numpy as np
import params as P
import power_247 as pw
from data_io import load_grid

B = P.BACKUP
FUEL_G_KWH = B["lca_g_mj"]["hvo"] * 3.6 / B["efficiency"]
YEARS = list(range(2027, 2027 + P.COSTS["horizon"]))


def path_mean(y, g2025):
    pts = sorted({2025: g2025, **{k: v for k, v in P.GRID_PATH_G_KWH.items() if v is not None}}.items())
    xs, ys = zip(*pts)
    return float(np.interp(y, xs, ys))


def run_scaled(port, scales, grid, wind, pv, load, biogas, carbon_aware):
    W, S, E, Pw, A = [np.array([v]) for v in port]
    gy = [P.WEATHER_YEARS.index(y) for y in P.GRID_YEARS]
    base = float(np.mean(grid["gb_intensity"]))
    res = {}
    for sc in scales:
        tot = dict(imp=0, impt=0, bk=0, hvo=0, b100=0, biogas=0, cost=0, lca_fuel=0, exp=0, ci_bk=0)
        for j, yi in enumerate(gy):
            gi = j
            ci = grid["gb_intensity"][gi] * sc
            prices = dict(hist=grid["price_norm"][gi])
            wm = W * wind[yi].sum(); sm = S * pv[yi].sum()
            strike = (wm * P.COSTS["ppa_wind_gbp_mwh"] + sm * P.COSTS["ppa_solar_gbp_mwh"]) / np.maximum(wm + sm, 1e-9)
            a = pw.dispatch_year(wind[yi], pv[yi], load, W, S, E, Pw, A, prices, dict(gb=ci), biogas, strike,
                                 gate=ci if carbon_aware else None, gate_g=FUEL_G_KWH)
            batt, bk, tank = pw.annual_fixed(E, A)
            fuel = a["hvo_l"] * B["hvo_gbp_l"] + a["b100_l"] * B["b100_gbp_l"]
            cost = (wm * P.COSTS["ppa_wind_gbp_mwh"] + sm * P.COSTS["ppa_solar_gbp_mwh"] + a["impcost_hist"] - a["expcap_hist"]
                    + batt + bk + tank + a["bk_mwh"] * B["vom_gbp_mwh"] + fuel)
            lca_f = (a["hvo_l"] * B["hvo_lhv_mj_l"] * B["lca_g_mj"]["hvo"] + a["b100_l"] * B["b100_lhv_mj_l"] * B["lca_g_mj"]["b100"]
                     + a["biogas_mwh"] * 3600 * B["lca_g_mj"]["biogas"]) / 1e6
            gen_tot = max(float((wm + sm)[0]), 1e-9)
            lca_r = ((wm * P.LCA["wind_g_kwh"] + sm * P.LCA["solar_g_kwh"]) / 1000 * np.clip((gen_tot - a["exp"]) / gen_tot, 0, 1)
                     + E * 1000 * P.LCA["battery_kg_per_kwh"] / P.LCA["battery_life"] / 1000)
            for k, v in (("imp", a["imp"]), ("impt", a["impt_gb"]), ("bk", a["bk_mwh"]), ("hvo", a["hvo_l"]), ("b100", a["b100_l"]),
                         ("biogas", a["biogas_mwh"]), ("cost", cost), ("lca_fuel", lca_f), ("exp", a["exp"])):
                tot[k] += float(v[0]) / len(gy)
            tot.setdefault("lca_ren", 0); tot["lca_ren"] += float(lca_r[0]) / len(gy)
        tot["total_t"] = tot["impt"] + tot["lca_fuel"] + tot["lca_ren"]
        tot["g_kwh"] = tot["total_t"] / (load * 8.76)
        tot["cfe"] = 1 - tot["imp"] / (load * 8760)
        tot["cost_gbp_mwh"] = tot["cost"] / (load * 8760)
        res[sc] = tot
    return res


def main():
    out = json.load(open(P.OUT / "power_247.json"))
    grid = load_grid()
    m25 = float(np.nanmean(grid["price"][-1]))
    grid["price_norm"] = grid["price"] / np.nanmean(grid["price"], axis=1, keepdims=True) * m25
    for k in ("price", "price_norm", "gb_intensity", "ne_intensity"):
        grid[k] = np.nan_to_num(grid[k], nan=float(np.nanmean(grid[k])))
    load = out["load_mw"]; biogas = out["biogas_mwh_yr"]
    wind, _, _ = pw.wind_fleet(P.POWER["wind_cf_central"]); pv = pw.pv_fleet()
    base = float(np.mean(grid["gb_intensity"])); g2025 = float(np.mean(grid["gb_intensity"][-1]))
    targets = {y: path_mean(y, g2025) for y in YEARS}
    grid_pts = sorted(set([base, g2025, 100.0, 75.0, 50.0, 30.0, 20.0, 10.0]))
    scales = [g / base for g in grid_pts]
    ports = {}
    for f in out["frontier"]:
        key = f"CFE {f['target']:.3f}"
        ports[key] = (f["wind_mw"], f["solar_mwp"], f["battery_mwh"], f["battery_mwh"] / P.POWER["battery_hours"], f["allowance_ml"] * 1e6)
    ports["website (no block)"] = (267.167, 89.056, 250.0, 100.0, 0.0)
    result = dict(fuel_g_kwh=FUEL_G_KWH, base_mean_g_kwh=base, g2025=g2025, path=targets, grid_points=grid_pts, portfolios={})
    comp_load = load
    for name, port in ports.items():
        rec = {}
        for mode in ("fossil-free", "carbon-aware"):
            if mode == "carbon-aware" and port[4] == 0:
                continue
            r = run_scaled(port, scales, grid, wind, pv, load, biogas, mode == "carbon-aware")
            pts = [(base * sc, v) for sc, v in r.items()]
            xs = np.array([p[0] for p in pts])
            def interp(key, g):
                return float(np.interp(g, xs, [p[1][key] for p in pts]))
            annual = [dict(year=y, grid_g=targets[y], dg_t=interp("total_t", targets[y]), cost=interp("cost_gbp_mwh", targets[y]),
                           cfe=interp("cfe", targets[y]), fuel_ml=(interp("hvo", targets[y]) + interp("b100", targets[y])) / 1e6,
                           comparator_t=comp_load * 8.76 * targets[y]) for y in YEARS]
            rec[mode] = dict(points={f"{base*sc:.1f}": v for sc, v in r.items()}, annual=annual,
                             cum_dg_kt=sum(a["dg_t"] for a in annual) / 1e3, cum_comp_kt=sum(a["comparator_t"] for a in annual) / 1e3,
                             mean_cost=float(np.mean([a["cost"] for a in annual])), mean_cfe=float(np.mean([a["cfe"] for a in annual])),
                             mean_fuel_ml=float(np.mean([a["fuel_ml"] for a in annual])))
        result["portfolios"][name] = rec
    # grid intensity in the hours the block runs (fossil-free rule, selected 100% portfolio, observed years)
    json.dump(result, open(P.OUT / "trajectory.json", "w"), indent=2, default=float)
    print("fuel g/kWh", round(FUEL_G_KWH, 1), "base", round(base, 1), "2025", round(g2025, 1))
    for name, rec in result["portfolios"].items():
        for mode, v in rec.items():
            print(f"{name:22s} {mode:13s} cum DG {v['cum_dg_kt']:7.0f} kt  grid campus {v['cum_comp_kt']:7.0f} kt  mean cost {v['mean_cost']:6.1f}  cfe {v['mean_cfe']:.3f}  fuel {v['mean_fuel_ml']:.1f} ML")


if __name__ == "__main__":
    main()
