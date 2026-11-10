#!/usr/bin/env python3
"""Design case versus QTS Cambois / Stargate UK: emissions on two bases, 25-year path, water, jobs and GPU economics
(25-year horizon matching the 20-25-year life of the contracted wind and solar)."""
import json
import numpy as np
import params as P
from compare_econ import gpu_npv, grid_lca, block_water_m3

C = P.COMPUTE; B = P.BACKUP


def main():
    d = json.load(open(P.OUT / "design.json")); dt = json.load(open(P.OUT / "design_trajectory.json"))
    hc = json.load(open(P.OUT / "heat_community.json")); pw = json.load(open(P.OUT / "power_247.json"))
    s = d["selected"]; L = d["annual_load_gwh"]; base = dt["base_mean"]; g25 = dt["g2025"]
    nc = sum(P.COSTS["non_commodity_gbp_mwh"].values())
    cam = P.COMPARATORS["QTS Cambois"]
    twh_gw = 8.76 * cam["utilisation"] * cam["pue"]
    dc_share = P.NETWORK["it_mw"] * P.NETWORK["it_utilisation"] * P.NETWORK["pue"] / d["load_mw"]
    it_gw = P.NETWORK["it_mw"] / 1000
    table = {}
    for name, g in (("2018-2025 observed", base), ("2025", g25), ("2030 (Clean Power 2030)", 50.0), ("2035 (CCC)", 10.0)):
        op = s["import_t"] * g / base
        lca = op * 1.2 + s["import_gwh"] * 12.0 + s["lca_t"]
        table[name] = {"Grid campus": dict(op_g=g, lca_g=grid_lca(g), op_mt_gw=twh_gw * g / 1000, lca_mt_gw=twh_gw * grid_lca(g) / 1000),
                       "Digital Gardens": dict(op_g=op / (L * 1e3) * 1e3, lca_g=lca / (L * 1e3) * 1e3, op_t=op, lca_t=lca,
                                               op_mt_gw=op * dc_share / it_gw / 1e6, lca_mt_gw=lca * dc_share / it_gw / 1e6)}
    twin_twh = it_gw * twh_gw
    cam_twh = cam["it_mw"] / 1000 * twh_gw
    sg = P.COMPARATORS["Stargate UK (Cobalt Park)"]; kw = C["products"]["GB300 NVL72"]["kw_per_gpu"]
    absolute = dict(twin=dict(twh=twin_twh, op_t=twin_twh * base * 1e3, lca_t=twin_twh * grid_lca(base) * 1e3),
                    cambois=dict(twh=cam_twh, op_mt=cam_twh * base / 1e3, lca_mt=cam_twh * grid_lca(base) / 1e3,
                                 cum_op_mt=sum(cam_twh * r["grid_g"] for r in dt["annual"]) / 1e3,
                                 cum_lca_mt=sum(cam_twh * grid_lca(r["grid_g"]) for r in dt["annual"]) / 1e3),
                    stargate={k: dict(gpus=sg[k], it_mw=sg[k] * kw / 1000, op_kt=sg[k] * kw / 1e6 * 8.76 * 0.9 * 1.2 * base)
                              for k in ("gpus_initial", "gpus_potential")})
    led = hc["ledger_full"]; ledl = hc["ledger_limited"]
    net = dict(dg_lca_kt_yr=table["2018-2025 observed"]["Digital Gardens"]["lca_t"] / 1e3, reductions_full_kt=led["total_t"] / 1e3,
               reductions_limited_kt=ledl["total_t"] / 1e3, cum_reductions_full_kt=led["total_t"] * 25 / 1e3, cum_reductions_limited_kt=ledl["total_t"] * 25 / 1e3)
    net["net_full_kt_yr"] = net["dg_lca_kt_yr"] - net["reductions_full_kt"]
    net["reductions_weighted_kt"] = hc["ledger_weighted"]["total_t"] / 1e3
    net["cum_reductions_weighted_kt"] = hc["ledger_weighted"]["total_t"] * 25 / 1e3
    # economics
    prog = hc["programme"]; jb = hc["jobs"]
    excl = jb["by_sector"]["IT/data-centre operations"] + jb["by_sector"]["Renewables, battery and standby generation"]
    labour = jb["cost_gbp"] * (1 - excl / jb["total"])
    netc = prog["revenue_total"] - prog["opex_total"] - labour
    veh = dict(vehicle_payment_gbp=prog["vehicles"]["annual_finance_payment_gbp"], vehicle_years=tuple(prog["vehicles"]["payment_years"]))
    cam_elec = d["comparator"]["energy_gbp_mwh"] + nc - cam["aigz_discount_gbp_mwh"]
    twin_load = P.NETWORK["it_mw"] * cam["utilisation"] * cam["pue"]
    res = {}
    for credit in ("full", "capped", "zero"):
        dg_elec = s[f"cost_{credit}"] + nc
        for product in C["products"]:
            for tier, start in C["price_start_usd"].items():
                twin = gpu_npv(product, start, cam_elec, twin_load, P.NETWORK["it_mw"])["npv_usd"]
                a = gpu_npv(product, start, dg_elec, d["load_mw"], P.NETWORK["it_mw"], community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)
                b = gpu_npv(product, start, dg_elec, d["load_mw"], P.NETWORK["it_mw"], label=1.0, community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)
                el_a = gpu_npv(product, start, dg_elec, d["load_mw"] - d["community_mw"], P.NETWORK["it_mw"])
                el_b = gpu_npv(product, start, dg_elec, d["load_mw"] - d["community_mw"], P.NETWORK["it_mw"], label=1.0)
                res[f"{credit}|{product}|{tier}"] = dict(dg_elec_gbp_mwh=dg_elec, twin_npv_musd=twin / 1e6, dg_npv_musd=a["npv_usd"] / 1e6,
                                                         premium=(twin - a["npv_usd"]) / (b["npv_usd"] - a["npv_usd"]),
                                                         premium_electricity_only=(twin - el_a["npv_usd"]) / (el_b["npv_usd"] - el_a["npv_usd"]),
                                                         share_of_price=(twin - a["npv_usd"]) / (b["npv_usd"] - a["npv_usd"]) / (start * C["products"][product]["price_factor"]),
                                                         elec_usd_gpu_h=a["elec_usd_per_gpu_h"])
    # AI Growth Zone discount: 'up to' GBP14/MWh, subject to eligibility and a 2030 review
    aigz = {}
    H = P.COSTS["horizon"]
    for case, yrs in (("full term (central)", H), ("to 2030 only", 4), ("none", 0)):
        path = [cam_elec + (0.0 if y < yrs else cam["aigz_discount_gbp_mwh"]) for y in range(H)]
        for tier, start in C["price_start_usd"].items():
            twin = gpu_npv("GB300 NVL72", start, cam_elec, twin_load, P.NETWORK["it_mw"], elec_by_year=path)["npv_usd"]
            dg_elec = s["cost_full"] + nc
            a = gpu_npv("GB300 NVL72", start, dg_elec, d["load_mw"], P.NETWORK["it_mw"], community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)
            b = gpu_npv("GB300 NVL72", start, dg_elec, d["load_mw"], P.NETWORK["it_mw"], label=1.0, community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)
            aigz[f"{case}|{tier}"] = dict(premium=(twin - a["npv_usd"]) / (b["npv_usd"] - a["npv_usd"]), cambois_mean_gbp_mwh=float(np.mean(path)))
    # surplus sold below the hourly price (capture-price cannibalisation / merchant discount)
    expv = {}
    mwh = d["load_mw"] * 8760
    for k in (1.0, 0.8, 0.6):
        dg_elec = s["cost_full"] + (1 - k) * s["export_revenue"] / mwh + nc
        twin = gpu_npv("GB300 NVL72", C["price_start_usd"]["on-demand"], cam_elec, twin_load, P.NETWORK["it_mw"])["npv_usd"]
        a = gpu_npv("GB300 NVL72", C["price_start_usd"]["on-demand"], dg_elec, d["load_mw"], P.NETWORK["it_mw"], community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)
        b = gpu_npv("GB300 NVL72", C["price_start_usd"]["on-demand"], dg_elec, d["load_mw"], P.NETWORK["it_mw"], label=1.0, community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)
        expv[f"{k:.1f}"] = dict(energy_gbp_mwh=dg_elec - nc, premium=(twin - a["npv_usd"]) / (b["npv_usd"] - a["npv_usd"]))
    xs = json.load(open(P.OUT / "export_scenarios.json")); exps = {}
    for name, x in xs.items():
        dg_elec = x["energy_gbp_mwh"] + nc; st = C["price_start_usd"]["on-demand"]
        twin = gpu_npv("GB300 NVL72", st, cam_elec, twin_load, P.NETWORK["it_mw"])["npv_usd"]
        a = gpu_npv("GB300 NVL72", st, dg_elec, d["load_mw"], P.NETWORK["it_mw"], community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)
        b = gpu_npv("GB300 NVL72", st, dg_elec, d["load_mw"], P.NETWORK["it_mw"], label=1.0, community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)
        exps[name] = dict(energy_gbp_mwh=x["energy_gbp_mwh"], premium=(twin - a["npv_usd"]) / (b["npv_usd"] - a["npv_usd"]))
    # break-even premium under adverse compute-market cases (GB300, on-demand)
    adverse = {}
    for name, kw in {"Sold 70%": dict(sold=0.70), "Sold 60%": dict(sold=0.60), "GPU capital +38%": dict(capex_mult=1.38), "Prices -20%": dict(price_mult=0.8),
                     "All four adverse": dict(capex_mult=1.38, sold=0.60, price_mult=0.8)}.items():
        st = C["price_start_usd"]["on-demand"]; dg_elec = s["cost_full"] + nc
        twin = gpu_npv("GB300 NVL72", st, cam_elec, twin_load, P.NETWORK["it_mw"], **kw)["npv_usd"]
        a = gpu_npv("GB300 NVL72", st, dg_elec, d["load_mw"], P.NETWORK["it_mw"], community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh, **kw)
        b = gpu_npv("GB300 NVL72", st, dg_elec, d["load_mw"], P.NETWORK["it_mw"], label=1.0, community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh, **kw)
        adverse[name] = dict(premium=(twin - a["npv_usd"]) / (b["npv_usd"] - a["npv_usd"]), dg_npv_musd=a["npv_usd"] / 1e6, twin_npv_musd=twin / 1e6)
    sens = {}
    base_kw = dict(community_capex_gbp=prog["capex_total"], community_net_gbp=netc, label=0.5, **veh)
    for name, kw in {"Central": {}, "GPU capital +38%": dict(capex_mult=1.38), "Sold 70%": dict(sold=0.70), "Sold 60%": dict(sold=0.60),
                     "Prices -20%": dict(price_mult=0.8), "All four adverse": dict(capex_mult=1.38, sold=0.60, price_mult=0.8)}.items():
        for tier, start in C["price_start_usd"].items():
            for path, dec in C["generation_paths"].items():
                sens[f"{name}|{tier}|{path}"] = gpu_npv("GB300 NVL72", start, s["cost_full"] + nc, d["load_mw"], P.NETWORK["it_mw"], decline=dec, **{**base_kw, **kw})["npv_usd"] / 1e6
    lo, hi = 1.0, 40.0
    for _ in range(60):
        m = (lo + hi) / 2
        v = gpu_npv("GB300 NVL72", m, s["cost_full"] + nc, d["load_mw"], P.NETWORK["it_mw"], community_capex_gbp=prog["capex_total"], community_net_gbp=netc, **veh)["npv_usd"]
        lo, hi = (m, hi) if v < 0 else (lo, m)
    water = dict(dg_cooling_m3=0.0, cambois_cooling_m3=0.0, block_test_m3=block_water_m3(d["test_mwh"] * 3600 / (B["efficiency"] * B["hvo_lhv_mj_l"])))
    out = dict(table=table, absolute=absolute, net=net, dc_share=dc_share, cum=dt["cum"], economics=dict(premium=res, sensitivity_musd=sens,
               cambois_delivered=cam_elec, dg_delivered=s["cost_full"] + nc, community_capex=prog["capex_total"], community_net=netc,
               community_labour=labour, breakeven_start_gb300=(lo + hi) / 2, aigz=aigz, export_value=expv, export_scenarios=exps, adverse_premium=adverse), water=water,
               jobs=dict(dg_data_centre_energy=excl, dg_data_centre_energy_per_mw=excl / P.NETWORK["it_mw"],
                         dg_it_ops=jb["by_sector"]["IT/data-centre operations"], dg_community=jb["total"] - excl, dg=jb["total"], dg_per_mw=jb["total"] / P.NETWORK["it_mw"], cambois=cam["operational_jobs"], cambois_per_mw=cam["operational_jobs"] / cam["it_mw"]),
               block=dict(test_mwh=d["test_mwh"], test_fuel_ml=d["test_mwh"] * 3600 / (B["efficiency"] * B["hvo_lhv_mj_l"]) / 1e6,
                          nox_t=d["test_mwh"] * B["nox_kg_mwh"] / 1000, standby_gbp=d["standby_gbp"], outage=d["outage"]))
    json.dump(out, open(P.OUT / "design_econ.json", "w"), indent=2, default=float)
    for k, v in table.items():
        print(k, {kk: {x: round(y, 3) for x, y in vv.items()} for kk, vv in v.items()})
    print("net", {k: round(v, 1) for k, v in net.items()})
    print("absolute", json.dumps(absolute, default=float)[:600])
    print("delivered DG", round(s["cost_full"] + nc, 1), "Cambois", round(cam_elec, 1), "community capex", round(prog["capex_total"] / 1e6), "net", round(netc / 1e6, 1))
    for k, v in res.items():
        print(k, {kk: round(vv, 3) for kk, vv in v.items()})
    print("breakeven GB300 start", round((lo + hi) / 2, 2))
    print("sens", {k: round(v) for k, v in sens.items() if "held" in k})


if __name__ == "__main__":
    main()
