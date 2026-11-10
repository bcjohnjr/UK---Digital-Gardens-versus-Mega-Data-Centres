#!/usr/bin/env python3
"""Assertions on the principal balances and results.
Run after: power_247.py design, design_trajectory.py, heat_community.py, design_econ.py."""
import json, math
import numpy as np
import params as P

d = json.load(open(P.OUT / "design.json")); hc = json.load(open(P.OUT / "heat_community.json"))
de = json.load(open(P.OUT / "design_econ.json")); dt = json.load(open(P.OUT / "design_trajectory.json"))
z = np.load(P.OUT / "design_grid.npz")
n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


S = d["selected"]; L = d["annual_load_gwh"]
# ---- load and design selection
check(abs(sum(r["it_mw"] for r in hc["heat"]["nodes"]) - P.NETWORK["it_mw"]) < 1e-3, "node IT sums to network IT")
check(hc["heat"]["facts"]["population"] == 20966, "population 20,966")
check(abs(L - d["load_mw"] * 8.76) < 1e-6, "annual load = mean load x 8760 h")
check(S["battery_mwh"] <= P.COSTS["battery_max_mwh"], "battery within the reasonable-size limit")
check(S["gen_ratio"] <= P.COSTS["sellback_limit"] + 1e-9, "generation within twice consumption")
check(S["self_supply"] >= P.COSTS["self_supply_target"] - 1e-9, "self-supply target met")
check(abs(1 - S["import_gwh"] / L - S["self_supply"]) < 1e-6, "self-supply = 1 - imports / load")
ok = (z["E"] <= P.COSTS["battery_max_mwh"]) & (z["gen"] <= P.COSTS["sellback_limit"] * L * 1e3 + 1e-6) & (z["cfe"] >= P.COSTS["self_supply_target"] - 1e-9)
check(ok.any() and abs(z["cost_full"][ok].min() - S["cost_full"]) < 1e-6, "design is the least-cost feasible portfolio")
check(S["cost_full"] <= S["cost_capped"] <= S["cost_zero"], "cost rises as export credit falls")
fr = d["frontier"]
for a, b in zip(fr, fr[1:]):
    check(b["cost_full"] >= a["cost_full"] - 1e-9, "frontier cost non-decreasing")
for f in fr:
    check(f["self_supply"] >= f["target"] - 1e-9, "frontier portfolio meets its target")
check(abs(d["sixteen_year"]["mean"] - np.mean(d["sixteen_year"]["by_year"])) < 1e-9, "16-year mean consistent")
check(d["wind_tests"]["0.253"]["mean"] < d["wind_tests"]["0.3"]["mean"] < d["wind_tests"]["raw"]["mean"] < d["wind_tests"]["0.36"]["mean"], "self-supply rises with wind yield")
# ---- backup block only on grid failure
Lpm = 3600 / (P.BACKUP["efficiency"] * P.BACKUP["hvo_lhv_mj_l"])
tank_h = P.BACKUP["tank_days"] * 24 * P.BACKUP["mw"] / d["load_mw"]
for o in d["outage"]:
    check(tank_h <= o["hours"] <= tank_h * 1.15, f"islanded autonomy ~ tank days at full load in {o['year']}")
for o in d["outage_with_renewables"]:
    check(o["hours"] >= 720, f"30-day autonomy if renewables islanded too, {o['year']}")
check(d["raw_wind"]["reoptimised"]["self_supply"] >= P.COSTS["self_supply_target"], "raw-wind re-optimised design meets target")
check(abs(S["export_capture_gbp_mwh"] - S["export_revenue"] / (S["export_gwh"] * 1e3)) < 1e-9, "capture price")
check(abs(de["block"]["test_mwh"] - P.BACKUP["mw"] * P.BACKUP["test_hours_per_year"]) < 1e-9, "test running = MW x hours")
# ---- emissions consistency
dg = de["table"]["2018-2025 observed"]["Digital Gardens"]
check(abs(dg["op_t"] - S["import_t"]) < 1e-6, "operational emissions = imported electricity emissions")
check(abs(dg["op_g"] - dg["op_t"] / L) < 1e-9, "operational intensity = t / MWh x 1e3")
check(abs(sum(r["dg_lca_t"] for r in dt["annual"]) / 1e3 - dt["cum"]["dg_lca_kt"]) < 1e-6, "25-year DG life-cycle sum")
check(abs(sum(r["twin_lca_t"] for r in dt["annual"]) / 1e3 - dt["cum"]["twin_lca_kt"]) < 1e-6, "25-year grid-campus life-cycle sum")
check(len(dt["annual"]) == 25, "25-year horizon")
check(dt["cum"]["dg_lca_kt"] < dt["cum"]["twin_lca_kt"] and dt["cum"]["dg_op_kt"] < dt["cum"]["twin_op_kt"], "DG below grid campus on both bases")
check(abs(de["net"]["net_full_kt_yr"] - (de["net"]["dg_lca_kt_yr"] - de["net"]["reductions_full_kt"])) < 1e-9, "net = supply - reductions")
# ---- heat balance per node and in total
for r in hc["heat"]["nodes"]:
    tot = sum(r[k] for k in ("homes_gwh", "greenhouse_gwh", "ras_gwh", "seaweed_gwh", "digester_gwh", "drying_gwh", "river_gwh", "dry_cooler_gwh"))
    check(abs(tot - r["recoverable_gwh"]) / r["recoverable_gwh"] < 1e-6, f"heat balance {r['node']}")
    check(r["homes_gwh"] <= r["homes_demand_gwh"] + 1e-9, "homes served <= demand")
th = hc["heat"]["thermal"]
used = sum(th[k] for k in ("homes_gwh", "greenhouse_gwh", "ras_gwh", "seaweed_gwh", "digester_gwh", "drying_gwh"))
check(abs(used - th["used_gwh"]) < 1e-6, "used heat = sum of uses")
check(abs(th["used_share_of_recoverable"] - used / th["recoverable_gwh"]) < 1e-9, "used share of recoverable")
check(th["erf"] < th["used_share_of_it_heat"] < th["used_share_of_recoverable"] <= 1, "efficiency shares ordered")
check(abs(th["homes_gwh"] - th["homes_demand_gwh"]) < 1e-6, "every connected home fully served")
cd = hc["sensitivities"]["continuous drying contracts at every node"]
check(abs(cd["used_share_of_recoverable"] - 1) < 1e-9 and cd["dry_cooler_peak_mw"] < 1e-9, "continuous drying uses all recoverable heat")
check(cd["useful_energy_efficiency"] > th["useful_energy_efficiency"], "continuous drying raises efficiency")
check(hc["heat"]["rivers"]["dT_at_q95_if_all_to_river"] < 3.0, "river temperature rise below 3 K at Q95")
# ---- food, feed and seaweed
pop = hc["heat"]["facts"]["population"]
check(abs(hc["heat"]["facts"]["veg_t"] - 146 * pop / 1e3) < 1e-6, "146 kg fresh produce per resident")
check(abs(hc["heat"]["facts"]["seafood_t"] - 46 * pop / 1e3) < 1e-6, "46 kg seafood per resident")
fd = hc["feed"]
check(0 < fd["local_share_total"] <= 1 and fd["prawn_meal_t"] > 0 and fd["fish_meal_t"] > 0, "circular feed shares bounded, both meals used")
check(fd["seaweed_capacity_t_dw"] >= hc["heat"]["facts"]["asparagopsis_t_dw"], "farm nutrients sufficient for the seaweed")
check(fd["greenhouse_waste_t"] >= fd["greens_direct_t"], "greenhouse waste covers the green feed")
# ---- community ledger
for lk in ("ledger_full", "ledger_no_asparagopsis", "ledger_limited", "ledger_north_east_seaweed"):
    lg = hc[lk]
    check(abs(sum(lg["rows"].values()) - lg["total_t"]) < 1e-6, f"{lk} rows sum to total")
    check(abs(lg["percent"]["of_addressed_sectors"] - lg["total_t"] / lg["baselines"]["addressed_sectors_t"]) < 1e-9, f"{lk} percentage")
check(hc["ledger_full"]["total_t"] >= hc["ledger_no_asparagopsis"]["total_t"] >= hc["ledger_limited"]["total_t"], "ledger ordering")
check(abs(hc["ledger_full"]["baselines"]["residents_territorial_t"] - pop * 373e6 / 69.3e6) < 1, "territorial baseline")
# ---- farm fuel: all catchment farms, subsidy closes HVO-red diesel gap
FF = P.FARM_FUEL
lha = sum(FF["area_share"][k] * FF["red_l_per_ha"][k] for k in FF["area_share"])
check(abs(hc["ledger_full"]["farm_hvo_ml"] * 1e6 - FF["ne_farmed_ha"] * P.LIVESTOCK["catchment_share"] * lha) < 1, "farm fuel = catchment farmland x L/ha")
check(abs(hc["programme"]["opex"]["farm_hvo_subsidy"] - hc["ledger_full"]["farm_hvo_ml"] * 1e6 * (P.BACKUP["hvo_gbp_l"] - FF["red_diesel_gbp_l"])) < 1, "farm subsidy = litres x price gap")
check(abs(hc["ledger_north_east_seaweed"]["farm_hvo_ml"] / hc["ledger_full"]["farm_hvo_ml"] - 1 / P.LIVESTOCK["catchment_share"]) < 1e-9, "NE scope scales farm fuel")
# ---- vehicles
v = hc["programme"]["vehicles"]
check(v["total"] >= v["households"] and abs(v["total"] - v["existing"] - v["new_for_zero_car"]) < 1e-6, "vehicle programme counts")
check(abs(v["new_for_zero_car"] - v["households"] * P.MOBILITY["car_dist"][0]) < 1e-6, "zero-car households each receive one vehicle")
check(abs(v["bev"] + v["phev"] - v["total"]) < 1e-6, "BEV + PHEV = total")
r = v["finance_rate"]; N = v["finance_years"]
check(abs(v["annual_finance_payment_gbp"] - v["fleet_value_gbp"] * r / (1 - (1 + r) ** -N)) < 1, "annuity payment")
# ---- programme, jobs, economics
pc = hc["programme"]
check(abs(sum(pc["capex"].values()) - pc["capex_total"]) < 1e-3, "capex sums")
check(abs(sum(hc["jobs"]["by_sector"].values()) - hc["jobs"]["total"]) == 0, "jobs sum")
for k, p in de["economics"]["premium"].items():
    check(p["premium"] >= p["premium_electricity_only"] - 1e-9, "premium covers at least electricity")
for prod in ("GB300 NVL72", "Vera Rubin NVL72"):
    for tier in ("reservation", "on-demand"):
        a, b, c = (de["economics"]["premium"][f"{x}|{prod}|{tier}"]["premium"] for x in ("full", "capped", "zero"))
        check(a <= b <= c, "premium rises as export credit falls")
# ---- islanded network, export scenarios, river rule, weighted ledger, seafood shares
isl = json.load(open(P.OUT / "island_network.json")); xs = json.load(open(P.OUT / "export_scenarios.json"))
check(abs(sum(isl["node_load_mw"].values()) - isl["total_load_mw"]) / isl["total_load_mw"] < 1e-6, "node loads sum to network load")
check(isl["min_voltage_pu"] >= 1 - P.ISLAND["v_limit"] and isl["n1_min_voltage_pu"] >= 1 - P.ISLAND["v_limit"], "voltage within limits, N and N-1")
check(isl["max_loading"] <= 1.0 and isl["n1_worst_loading"] <= 1.0, "thermal loading within ampacity, N and N-1")
check(abs(isl["circuit_km"] - P.ISLAND["circuits"] * sum(k for _, _, k in P.ISLAND["routes"])) < 1e-9, "circuit-km")
check(isl["gt_n1"]["remaining_mw"] < isl["total_load_mw"], "loss of one GT requires battery and IT curtailment")
# Battery rating must be honoured in every turbine-trip adequacy claim.
n1 = isl["gt_n1"]
check(abs(n1["battery_power_mw"] - S["battery_mwh"] / P.POWER["battery_hours"]) < 1e-9, "four-hour battery power rating")
check(n1["battery_delivered_mw"] <= n1["battery_power_mw"] + 1e-9, "battery never exceeds its power rating")
check(abs(n1["immediate_unserved_mw"] - max(n1["shortfall_mw"] - n1["battery_power_mw"], 0)) < 1e-9, "unserved loss-of-generator power")
check(abs(n1["battery_duration_at_rated_power_h"] - P.POWER["battery_hours"]) < 1e-9, "battery duration at rated output")
check(n1["immediate_unserved_mw"] > 20 and n1["unserved_after_battery_mw"] > 45, "dispatch has immediate outage")
cen = xs["central: all surplus at hourly price"]
check(abs(cen["export_gwh"] - S["export_gwh"]) / S["export_gwh"] < 1e-6, "uncapped export scenario reproduces design")
for k, x in xs.items():
    check(x["energy_gbp_mwh"] >= cen["energy_gbp_mwh"] - 1e-9, f"export restriction never lowers cost: {k}")
rv = hc["heat"]["rivers"]; RR = P.RIVER_RULE
check(rv["peak_dT_haydon_k"] <= RR["dT_limit_k"] + 1e-9 and rv["peak_dT_bywell_k"] <= RR["dT_limit_k"] + 1e-9, "river rise within local limits")
check(all(rv["river_peak_by_node_mw"][P.NODE_LABEL[n]] == 0 for n in RR["no_discharge_nodes"]), "no discharge to the regulated North Tyne")
lw = hc["ledger_weighted"]
check(abs(lw["total_t"] - sum(v * P.TIER_WEIGHT[P.COMMUNITY_TIER[k]] for k, v in hc["ledger_full"]["rows"].items())) < 1e-6, "weighted ledger")
check(abs(P.AQUAFEED["finfish_share"] + P.AQUAFEED["prawn_share"] - 1.0) < 1e-12, "seafood species shares sum to 100%")
check(abs(fd["finfish_t"] + fd["prawn_t"] - hc["heat"]["facts"]["seafood_t"]) < 1e-6, "seafood mass balance closes")
sc = dt["scenarios"]
check(sc["slower (100 g 2030, 50 g 2035, 25 g 2040)"]["twin_lca_kt"] > sc["central (Clean Power 2030, CCC 2035)"]["twin_lca_kt"] > sc["faster (30 g 2030, 5 g 2035)"]["twin_lca_kt"], "grid-path ordering")
print(f"All {n} validation assertions passed")
