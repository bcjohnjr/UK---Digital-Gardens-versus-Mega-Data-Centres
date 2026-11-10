#!/usr/bin/env python3
"""25-year emissions and cost of the design portfolio (renewables -> battery -> grid; block on grid failure only) on the
GB decarbonisation path, against a grid campus at the same IT. Also replays the design under a fossil-free-first rule."""
import json
import numpy as np
import params as P
import power_247 as pw
from data_io import load_grid
from trajectory import path_mean, YEARS

B = P.BACKUP


def main():
    d = json.load(open(P.OUT / "design.json")); s = d["selected"]
    grid = load_grid(); m25 = float(np.nanmean(grid["price"][-1]))
    grid["price_norm"] = grid["price"] / np.nanmean(grid["price"], axis=1, keepdims=True) * m25
    for k in ("price", "price_norm", "gb_intensity"):
        grid[k] = np.nan_to_num(grid[k], nan=float(np.nanmean(grid[k])))
    load = d["load_mw"]; wind, _, _ = pw.wind_fleet(P.POWER["wind_cf_central"]); pv = pw.pv_fleet()
    gy = [P.WEATHER_YEARS.index(y) for y in P.GRID_YEARS]
    base = float(np.mean(grid["gb_intensity"])); g25 = float(np.mean(grid["gb_intensity"][-1]))
    W, S, E = [np.array([v]) for v in (s["wind_mw"], s["solar_mwp"], s["battery_mwh"])]
    imp_t = []      # import-weighted grid intensity is shape-dependent: compute at base scale, then scale linearly
    for j, yi in enumerate(gy):
        a = pw.dispatch_year(wind[yi], pv[yi], load, W, S, E, E / 4, np.zeros(1), dict(hist=grid["price_norm"][j]),
                             dict(gb=grid["gb_intensity"][j]), d["biogas_mwh_yr"] if "biogas_mwh_yr" in d else pw.biogas_mwh_per_year())
        imp_t.append(float(a["impt_gb"][0]))
    imp_t_base = float(np.mean(imp_t)); imp_g = imp_t_base / s["import_gwh"] / 1e3 * 1e3 if s["import_gwh"] else 0
    lca_fixed = s["lca_t"]
    twin_gwh = P.NETWORK["it_mw"] * P.COMPARATORS["QTS Cambois"]["utilisation"] * P.COMPARATORS["QTS Cambois"]["pue"] * 8.76
    rows = []
    for y in YEARS:
        g = path_mean(y, g25); sc = g / base
        dg_op = imp_t_base * sc
        rows.append(dict(year=y, grid_g=g, dg_op_t=dg_op, dg_lca_t=dg_op * 1.2 + s["import_gwh"] * 12.0 + lca_fixed,
                         twin_op_t=twin_gwh * g, twin_lca_t=twin_gwh * (g * 1.2 + 12.0)))
    def path_s(y, pts):
        xs = [2025] + sorted(pts); ys = [g25] + [pts[k] for k in sorted(pts)]
        return float(np.interp(y, xs, ys))
    scen = {}
    for name, pts in P.GRID_PATH_SCENARIOS.items():
        dg = tw = dgo = two = 0.0
        for y in YEARS:
            g = path_s(y, pts); sc = g / base; op = imp_t_base * sc
            dgo += op; dg += op * 1.2 + s["import_gwh"] * 12.0 + lca_fixed; two += twin_gwh * g; tw += twin_gwh * (g * 1.2 + 12.0)
        scen[name] = dict(dg_op_kt=dgo / 1e3, dg_lca_kt=dg / 1e3, twin_op_kt=two / 1e3, twin_lca_kt=tw / 1e3)
    out = dict(scenarios=scen, import_weighted_g_kwh_2018_2025=imp_g, base_mean=base, g2025=g25, annual=rows,
               cum=dict(dg_op_kt=sum(r["dg_op_t"] for r in rows) / 1e3, dg_lca_kt=sum(r["dg_lca_t"] for r in rows) / 1e3,
                        twin_op_kt=sum(r["twin_op_t"] for r in rows) / 1e3, twin_lca_kt=sum(r["twin_lca_t"] for r in rows) / 1e3),
               first_year=rows[0], year_2030=next(r for r in rows if r["year"] == 2030))
    json.dump(out, open(P.OUT / "design_trajectory.json", "w"), indent=2, default=float)
    print(json.dumps(out["cum"], indent=1), "import-weighted g/kWh", round(imp_g, 1), "base", round(base, 1))


if __name__ == "__main__":
    main()
