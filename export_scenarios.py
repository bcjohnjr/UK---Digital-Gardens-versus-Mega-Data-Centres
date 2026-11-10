#!/usr/bin/env python3
"""Value of the design portfolio's surplus under export caps (grid constraints at the contracted plants), merchant PPA price
discounts and constraint curtailment. Re-dispatches the selected portfolio hour by hour over 2018-2025."""
import json
import numpy as np
import params as P
import power_247 as pw
from data_io import load_grid


def main():
    d = json.load(open(P.OUT / "design.json")); s = d["selected"]
    grid = load_grid(); m25 = float(np.nanmean(grid["price"][-1]))
    grid["price_norm"] = grid["price"] / np.nanmean(grid["price"], axis=1, keepdims=True) * m25
    for k in ("price", "price_norm", "gb_intensity", "ne_intensity"):
        grid[k] = np.nan_to_num(grid[k], nan=float(np.nanmean(grid[k])))
    load = d["load_mw"]; wind, _, _ = pw.wind_fleet(P.POWER["wind_cf_central"]); pv = pw.pv_fleet(); biogas = pw.biogas_mwh_per_year()
    gy = [P.WEATHER_YEARS.index(y) for y in P.GRID_YEARS]; mwh = load * 8760
    W, S, E = [np.array([v]) for v in (s["wind_mw"], s["solar_mwp"], s["battery_mwh"])]
    base_exp = None; out = {}
    for name, sc in P.EXPORT_SCENARIOS.items():
        ev = []; ex = []; cu = []; peak = 0.0
        for j, yi in enumerate(gy):
            rec = {}
            a = pw.dispatch_year(wind[yi], pv[yi], load, W, S, E, E / 4, np.zeros(1), dict(hist=grid["price"][j], norm=grid["price_norm"][j]),
                                 dict(gb=grid["gb_intensity"][j]), biogas, export_cap=sc["cap_mw"], record=rec)
            ev.append(float(a["expval_norm"][0])); ex.append(float(a["exp"][0])); cu.append(float(a["cur"][0]))
            peak = max(peak, max(rec["surplus"]))
        val = np.mean(ev) * sc["price_share"] * (1 - sc["constraint"])
        energy = s["cost_full"] + (s["export_revenue"] - val) / mwh
        out[name] = dict(export_gwh=np.mean(ex) * (1 - sc["constraint"]) / 1e3, curtailed_gwh=(np.mean(cu) + np.mean(ex) * sc["constraint"]) / 1e3,
                         export_value_gbp=val, energy_gbp_mwh=energy, peak_export_mw=peak, **sc)
    json.dump(out, open(P.OUT / "export_scenarios.json", "w"), indent=2, default=float)
    for k, v in out.items():
        print(f"{k:62s} sold {v['export_gwh']:6.0f} GWh curtailed {v['curtailed_gwh']:5.0f} GWh value £{v['export_value_gbp']/1e6:5.1f}m energy £{v['energy_gbp_mwh']:.1f}/MWh peak {v['peak_export_mw']:.0f} MW")


if __name__ == "__main__":
    main()
