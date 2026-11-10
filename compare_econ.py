#!/usr/bin/env python3
"""Head-to-head comparison with QTS Cambois and Stargate UK, emissions per GW of IT, water, jobs and GPU economics.

Both comparators are grid-supplied campuses in the North East AI Growth Zone. Their electricity emissions are counted on
a location basis with the hourly North East England carbon intensity (2018-2025), and, separately, on a market basis
with annual certificate matching. Digital Gardens is counted on its hourly-matched portfolio: imports at the hourly
regional intensity plus the life-cycle emissions of its contracted wind, solar and battery (all output, including what
it sells). The GPU business is modelled as in the British Columbia study, with prices that fall within each hardware
generation; the break-even clean-compute premium is solved exactly because NPV is linear in the premium.
"""
import json
import numpy as np
import params as P

C = P.COMPUTE; FX = P.GBP_PER_USD
WATER_M3_MWH = dict(gas=0.75, coal=2.60, biomass=2.09, nuclear=1.02, other=0.75, imports=0.0, wind=0.0, solar=0.004, hydro=0.0)
# median operational consumption factors (Macknick et al. 2012): NGCC tower 198 gal/MWh, coal tower 687, biomass steam 553,
# nuclear once-through 269 (GB nuclear stations are seawater-cooled, so this water is not freshwater); upper-bound screen.


def load():
    pw = json.load(open(P.OUT / "power_247.json")); hc = json.load(open(P.OUT / "heat_community.json"))
    return pw, hc


def selected(pw, target):
    return next(f for f in pw["frontier"] if abs(f["target"] - target) < 1e-9)


def emissions(pw, hc, tr, target):
    """Emissions per GW of IT and absolute, on an operational (location-based scope 2 plus fossil combustion) and a life-cycle
    basis, for 2018-2025 observed grid intensity, the 2025 level and the Clean Power 2030 level."""
    s = selected(pw, target)
    load_gwh = pw["annual_load_gwh"]
    dc_share = P.NETWORK["it_mw"] * P.NETWORK["it_utilisation"] * P.NETWORK["pue"] / pw["load_mw"]
    it_gw = P.NETWORK["it_mw"] / 1000
    cam = P.COMPARATORS["QTS Cambois"]
    twh_per_gw = 8.76 * cam["utilisation"] * cam["pue"]
    key = f"CFE {target:.3f}"
    pts = tr["portfolios"][key]
    levels = {"2018-2025 observed": tr["base_mean_g_kwh"], "2025": tr["g2025"], "2030 (Clean Power 2030)": 50.0, "2035 (CCC)": 10.0}
    def dg_at(mode, g):
        p = pts[mode]["points"]; xs = np.array([float(k) for k in p]); order = np.argsort(xs)
        f = lambda kk: float(np.interp(g, xs[order], [list(p.values())[i][kk] for i in order]))
        op = f("impt"); lca = f("total_t")
        return dict(op_t=op, lca_t=lca, op_g=op / (load_gwh * 1e3) * 1e3, lca_g=lca / (load_gwh * 1e3) * 1e3,
                    cfe=f("cfe"), fuel_ml=(f("hvo") + f("b100")) / 1e6, cost=f("cost_gbp_mwh"))
    table = {}
    for name, g in levels.items():
        row = {"Grid campus (QTS Cambois / Stargate UK type)": dict(op_g=g, lca_g=grid_lca(g),
                                                                      op_mt_per_gw=twh_per_gw * g / 1000, lca_mt_per_gw=twh_per_gw * grid_lca(g) / 1000)}
        for mode in ("fossil-free", "carbon-aware"):
            d = dg_at(mode, g)
            d.update(op_mt_per_gw=d["op_t"] * dc_share / it_gw / 1e6, lca_mt_per_gw=d["lca_t"] * dc_share / it_gw / 1e6)
            row[f"Digital Gardens, {mode} rule"] = d
        table[name] = row
    cam_twh = cam["it_mw"] / 1000 * twh_per_gw
    sg = P.COMPARATORS["Stargate UK (Cobalt Park)"]
    kw = P.COMPUTE["products"]["GB300 NVL72"]["kw_per_gpu"]
    g0 = tr["base_mean_g_kwh"]
    absolute = dict(
        cambois=dict(it_mw=cam["it_mw"], twh=cam_twh, op_mt=cam_twh * g0 / 1000, lca_mt=cam_twh * grid_lca(g0) / 1000),
        stargate={k: dict(gpus=sg[k], it_mw=sg[k] * kw / 1000, twh=sg[k] * kw / 1e6 * 8.76 * sg["utilisation"] * sg["pue"],
                          op_kt=sg[k] * kw / 1e6 * 8.76 * sg["utilisation"] * sg["pue"] * g0) for k in ("gpus_initial", "gpus_potential")},
        twin_at_dg_it=dict(twh=P.NETWORK["it_mw"] / 1000 * twh_per_gw, op_t=P.NETWORK["it_mw"] / 1000 * twh_per_gw * g0 * 1e3,
                           lca_t=P.NETWORK["it_mw"] / 1000 * twh_per_gw * grid_lca(g0) * 1e3),
        dg=dict(it_mw=P.NETWORK["it_mw"], load_gwh=load_gwh, op_t=s["mean_impt_gb"], lca_t=s["mean_impt_gb"] + s["mean_lca_t"],
                biogenic_t=s["mean_biogenic_t"], fuel_ml=(s["mean_hvo_l"] + s["mean_b100_l"]) / 1e6),
    )
    # 25-year cumulative on the GB path, both bases, comparator at the twin's load
    twin_gwh = absolute["twin_at_dg_it"]["twh"] * 1e3
    cum = {}
    for mode in ("fossil-free", "carbon-aware"):
        ann = pts[mode]["annual"]
        cum[mode] = dict(dg_lca_kt=sum(dg_at(mode, a["grid_g"])["lca_t"] for a in ann) / 1e3,
                         dg_op_kt=sum(dg_at(mode, a["grid_g"])["op_t"] for a in ann) / 1e3,
                         mean_cost=float(np.mean([dg_at(mode, a["grid_g"])["cost"] for a in ann])),
                         mean_cfe=float(np.mean([dg_at(mode, a["grid_g"])["cfe"] for a in ann])),
                         mean_fuel_ml=float(np.mean([dg_at(mode, a["grid_g"])["fuel_ml"] for a in ann])))
    ann = pts["fossil-free"]["annual"]
    cum["grid campus at the same IT"] = dict(op_kt=sum(twin_gwh * a["grid_g"] for a in ann) / 1e3,
                                             lca_kt=sum(twin_gwh * grid_lca(a["grid_g"]) for a in ann) / 1e3)
    cum["QTS Cambois 720 MW"] = dict(op_kt=sum(cam_twh * 1e3 * a["grid_g"] for a in ann) / 1e3,
                                      lca_kt=sum(cam_twh * 1e3 * grid_lca(a["grid_g"]) for a in ann) / 1e3)
    return table, absolute, cum, dc_share


def block_water_m3(fuel_l):
    """Demineralised water for NOx-control water injection on liquid fuel (about 1 kg per kg of fuel) plus heat-recovery
    steam generator make-up (about 2% of steam flow, folded into the same factor); the steam cycle uses an air-cooled
    condenser, so no cooling water is evaporated."""
    return fuel_l * 0.78 * 1.0 / 1000.0


GRID_LCA_UPSTREAM = 0.20      # gas upstream and supply-chain share added to operational intensity (as in the BC study)
GRID_LCA_EMBODIED = 12.0      # g/kWh embodied in low-carbon generation (IPCC AR5 medians: wind 11, nuclear 12)


def grid_lca(op_g):
    return op_g * (1 + GRID_LCA_UPSTREAM) + GRID_LCA_EMBODIED


def price_path(start, y, decline, product):
    cy = (y - 1) % C["cycle_years"]
    return max(start * (1 - decline) ** ((y - 1) // C["cycle_years"]) + C["price_step_usd_per_year"] * cy, 0.5) * C["products"][product]["price_factor"]


def gpu_npv(product, start, elec_gbp_mwh, load_mw, it_mw, label=0.0, label_share=1.0, decline=0.0, sold=None,
            community_capex_gbp=0.0, community_net_gbp=0.0, vehicle_payment_gbp=0.0, vehicle_years=(), capex_mult=1.0, price_mult=1.0,
            elec_by_year=None):
    pr = C["products"][product]; sold = C["sold"] if sold is None else sold
    gpus = it_mw * 1000 / pr["kw_per_gpu"]
    gpu_capex = gpus * pr["capex_usd_per_gpu"] * capex_mult
    fac = it_mw * C["facility_capex_usd_mw"]
    r = C["wacc"]; Y = C["horizon"]
    cash = [-(fac + gpu_capex + community_capex_gbp / FX)]
    for y in range(1, Y + 1):
        cy = (y - 1) % C["cycle_years"]
        price = price_path(start * price_mult, y, decline, product)
        hours = gpus * 8760 * sold
        rev = hours * (price + label * label_share)
        elec = (elec_by_year[y - 1] if elec_by_year is not None else elec_gbp_mwh) * load_mw * 8760 / FX
        opex = gpu_capex * C["maintenance_frac"] + (gpu_capex + fac) * C["insurance_frac"] + it_mw * C["fte_per_mw"] * C["usd_per_fte"]
        ebitda = rev - elec - opex + community_net_gbp / FX
        end = cy == C["cycle_years"] - 1 or y == Y
        resid = gpu_capex * (1 - (1 - C["residual"]) * (cy + 1) / C["cycle_years"]) if end else 0.0
        capex = gpu_capex if (end and y < Y) else 0.0
        if y in vehicle_years:
            ebitda -= vehicle_payment_gbp / FX                       # vehicle finance (84 months, each 12-year vehicle cycle)
        dep = gpu_capex * (1 - C["residual"]) / C["cycle_years"] + fac / Y
        tax = max(0.0, (ebitda - dep) * C["tax"])
        cash.append(ebitda - tax - capex + resid)
    npv = sum(c / (1 + r) ** i for i, c in enumerate(cash))
    return dict(npv_usd=npv, gpus=gpus, elec_usd_per_gpu_h=elec_gbp_mwh * load_mw * 8760 / FX / (gpus * 8760 * sold))


def economics(pw, hc, target, dg_energy_override=None):
    s = selected(pw, target)
    nc = pw["non_commodity_gbp_mwh"]
    dg_elec = (s["cost_gbp_mwh"] if dg_energy_override is None else dg_energy_override) + nc
    comp = pw["comparator_at_dg_load"]["price_norm"]
    cam = P.COMPARATORS["QTS Cambois"]
    cam_elec = comp["energy_gbp_mwh"] + nc - cam["aigz_discount_gbp_mwh"]
    it = P.NETWORK["it_mw"]
    dg_load = pw["load_mw"]; twin_load = it * cam["utilisation"] * cam["pue"]
    prog = hc["programme"]; jb = hc["jobs"]
    community_labour = jb["cost_gbp"] * (1 - (jb["by_sector"]["IT/data-centre operations"] + jb["by_sector"]["Renewables, battery and standby generation"]) / jb["total"])
    net = prog["revenue_total"] - prog["opex_total"] - community_labour
    capex = prog["capex_total"]
    veh = dict(vehicle_payment_gbp=prog["vehicles"]["annual_finance_payment_gbp"], vehicle_years=tuple(prog["vehicles"]["payment_years"]))
    res = {}
    for product in C["products"]:
        for tier, start in C["price_start_usd"].items():
            for path, dec in C["generation_paths"].items():
                kw = dict(decline=dec)
                twin = gpu_npv(product, start, cam_elec, twin_load, it, **kw)["npv_usd"]
                dg0 = gpu_npv(product, start, dg_elec, dg_load, it, community_capex_gbp=capex, community_net_gbp=net, **veh, **kw)
                dg1 = gpu_npv(product, start, dg_elec, dg_load, it, label=1.0, community_capex_gbp=capex, community_net_gbp=net, **veh, **kw)
                slope = dg1["npv_usd"] - dg0["npv_usd"]
                prem = (twin - dg0["npv_usd"]) / slope
                res[f"{product}|{tier}|{path}"] = dict(twin_npv_musd=twin / 1e6, dg_npv_musd=dg0["npv_usd"] / 1e6, gap_musd=(twin - dg0["npv_usd"]) / 1e6,
                                                       premium_all_hours=prem, premium_half_hours=2 * prem, gpus=dg0["gpus"],
                                                       dg_elec_usd_gpu_h=dg0["elec_usd_per_gpu_h"], premium_share_of_price=prem / (start * C["products"][product]["price_factor"]))
    # electricity-only premium (no community programme) to separate the two effects
    ele_only = {}
    for product in C["products"]:
        start = C["price_start_usd"]["on-demand"]
        twin = gpu_npv(product, start, cam_elec, twin_load, it)["npv_usd"]
        a = gpu_npv(product, start, dg_elec, dg_load - pw["community_mw"], it)
        b = gpu_npv(product, start, dg_elec, dg_load - pw["community_mw"], it, label=1.0)
        ele_only[product] = (twin - a["npv_usd"]) / (b["npv_usd"] - a["npv_usd"])
    # sensitivities for the GB300 business with a US$0.50 premium on all hours (on-demand and reservation)
    sens = {}
    base = dict(community_capex_gbp=capex, community_net_gbp=net, label=0.5, **veh)
    cases = {"Central": {}, "GPU capital +38%": dict(capex_mult=1.38), "Sold 70%": dict(sold=0.70), "Sold 60%": dict(sold=0.60),
             "Prices -20%": dict(price_mult=0.8), "All four adverse": dict(capex_mult=1.38, sold=0.60, price_mult=0.8)}
    for name, kw in cases.items():
        for tier, start in C["price_start_usd"].items():
            for path, dec in C["generation_paths"].items():
                sens[f"{name}|{tier}|{path}"] = gpu_npv("GB300 NVL72", start, dg_elec, dg_load, it, decline=dec, **{**base, **kw})["npv_usd"] / 1e6
    # Vera Rubin: starting on-demand price needed for the Digital Gardens business to break even (NPV = 0), prices held
    lo, hi = 1.0, 40.0
    for _ in range(60):
        m = (lo + hi) / 2
        v = gpu_npv("Vera Rubin NVL72", m, dg_elec, dg_load, it, community_capex_gbp=capex, community_net_gbp=net, **veh)["npv_usd"]
        lo, hi = (m, hi) if v < 0 else (lo, m)
    rubin_be = (lo + hi) / 2
    lo, hi = 1.0, 40.0
    for _ in range(60):
        m = (lo + hi) / 2
        v = gpu_npv("GB300 NVL72", m, dg_elec, dg_load, it, community_capex_gbp=capex, community_net_gbp=net, **veh)["npv_usd"]
        lo, hi = (m, hi) if v < 0 else (lo, m)
    gb_be = (lo + hi) / 2
    return dict(dg_delivered_gbp_mwh=dg_elec, cambois_delivered_gbp_mwh=cam_elec, dg_load_mw=dg_load, twin_load_mw=twin_load,
                community_capex_gbp=capex, community_net_gbp=net, community_labour_gbp=community_labour,
                premium=res, premium_electricity_only=ele_only, sensitivity_musd=sens,
                breakeven_start_price_usd=dict(vera_rubin=rubin_be, gb300=gb_be))


def main(target=None):
    from heat_community import P_SELECTED_CFE
    target = P_SELECTED_CFE if target is None else target
    pw, hc = load(); tr = json.load(open(P.OUT / "trajectory.json"))
    table, absolute, cum, dc_share = emissions(pw, hc, tr, target)
    s = selected(pw, target)
    cam = P.COMPARATORS["QTS Cambois"]
    water = dict(dg_cooling_m3=0.0, cambois_cooling_m3=0.0,
                 dg_block_fossil_free_m3=block_water_m3(s["mean_hvo_l"] + s["mean_b100_l"]),
                 dg_block_carbon_aware_m3=block_water_m3(cum["carbon-aware"]["mean_fuel_ml"] * 1e6))
    jb = hc["jobs"]
    jobs_cmp = dict(dg_total=jb["total"], dg_per_mw=jb["total"] / P.NETWORK["it_mw"],
                    cambois_operational=cam["operational_jobs"], cambois_per_mw=cam["operational_jobs"] / cam["it_mw"])
    econ = economics(pw, hc, target)
    econ_ca = economics(pw, hc, target, dg_energy_override=cum["carbon-aware"]["mean_cost"])
    nox = dict(block_t=s["mean_bk_mwh"] * P.BACKUP["nox_kg_mwh"] / 1000)
    out = dict(target=target, emissions_table=table, absolute=absolute, cumulative_25y=cum, dc_share=dc_share, water=water, jobs=jobs_cmp,
               economics=econ, economics_carbon_aware=econ_ca, nox=nox)
    json.dump(out, open(P.OUT / "compare_econ.json", "w"), indent=2, default=float)
    for lvl, row in table.items():
        print(lvl)
        for k, v in row.items():
            print(f"   {k:48s} op {v['op_g']:6.1f} g  lca {v['lca_g']:6.1f} g  op Mt/GW {v['op_mt_per_gw']:.3f}  lca Mt/GW {v['lca_mt_per_gw']:.3f}")
    print("cum", json.dumps(cum, default=float))
    print("absolute", json.dumps(absolute, default=float)[:900])
    print("water", water, "nox", nox, "jobs", jobs_cmp)
    for nm, e in (("fossil-free", econ), ("carbon-aware", econ_ca)):
        print(nm, "DG delivered", round(e["dg_delivered_gbp_mwh"], 1), "Cambois delivered", round(e["cambois_delivered_gbp_mwh"], 1),
              "community capex £m", round(e["community_capex_gbp"] / 1e6), "net £m/yr", round(e["community_net_gbp"] / 1e6, 1))
        for k, v in e["premium"].items():
            print("  ", k, {kk: round(vv, 3) for kk, vv in v.items() if kk in ("twin_npv_musd", "dg_npv_musd", "premium_all_hours", "premium_share_of_price", "dg_elec_usd_gpu_h")})
        print("   electricity-only premium", {k: round(v, 3) for k, v in e["premium_electricity_only"].items()}, "break-even start", {k: round(v, 2) for k, v in e["breakeven_start_price_usd"].items()})
    print("sens", {k: round(v) for k, v in econ["sensitivity_musd"].items() if "held" in k})


if __name__ == "__main__":
    main()
