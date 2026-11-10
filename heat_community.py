#!/usr/bin/env python3
"""Node-by-node hourly heat matching, circular aquaculture and seaweed, drying (contracted and bartered), river heat
rejection, the host-community carbon ledger with percentage reductions, programme costs and jobs.

For each of the eight nodes and each hour of 2010-2025, recoverable IT heat (85% of the IT draw, 15% lost in
distribution) goes first to every connected household: space heat from a degree-hour model on the node's own ERA5
temperature, hot water and hot-fill washing and cleaning at 60 C. A small heat pump in each home lifts the 45-55 C loop
to radiator and hot-water temperature, drawing its source heat from the loop. Then come the community greenhouses, the
fish and prawn farms, the red-seaweed (Asparagopsis) tanks fed by the farms' effluent, the digesters, and drying
contracts at that node (seasonal first, then stockpiled year-round feedstock). Heat cannot move between nodes. What is
left is rejected without evaporation: to the river within a 1 C fully mixed rise at Q95, otherwise by dry coolers.
"""
import json
import numpy as np
import params as P
from data_io import load_site, load_communities

H = P.HEAT; LV = P.LIVESTOCK; AF = P.AQUAFEED
RHO_CP = 4.186e3


def temps():
    return {n: load_site(P.NODE_LABEL[n], cols=("temperature_2m",))["temperature_2m"] for n in P.NODES}


def months_of_year():
    import pandas as pd
    idx = pd.date_range("2021-01-01", "2021-12-31 23:00", freq="h")
    return idx.month.to_numpy()


def dhw_kwh_per_household():
    return H["persons_per_household"] * H["dhw_l_person_day"] * 365 * 4.186 * (H["dhw_c"] - H["mains_c"]) / 3600


def calibrate_ua(T):
    """UA (kW/K per household) giving useful space heat + hot water equal to the Ofgem typical domestic gas consumption
    (11,500 kWh/yr) times boiler efficiency, at Hexham's 2010-2025 ERA5 temperatures."""
    t = T["hexham"]; ny = t.shape[0]
    dh = np.maximum(0, H["base_c"] - t).sum() / ny
    return (11500.0 * H["boiler_eff"] - dhw_kwh_per_household()) / dh


def loop_share(lift_share):
    """Loop heat per unit of delivered heat when a heat pump (COP) supplies lift_share of it from the loop."""
    return (1 - lift_share) + lift_share * (1 - 1 / H["hp_cop"]), lift_share / H["hp_cop"]


# ----------------------------------------------------------------------------------------------- seaweed and feed
def herds(scope="catchment"):
    share = LV["catchment_share"] if scope == "catchment" else 1.0
    return LV["ne_dairy"] * share, LV["ne_beef"] * share


def asparagopsis_need_t(dairy, beef):
    d, b = LV["asp_dmi_kg_day"]["dairy"], LV["asp_dmi_kg_day"]["beef"]
    days_d = 365 * LV["asp_coverage"]["dairy"]; days_b = 365 * LV["asp_coverage"]["beef"]
    return (dairy * d * days_d + beef * b * days_b) * LV["asp_dose_dm"] / LV["asp_bromoform_retention"] / 1000      # t dry weight


def feed_loop(seafood_t, veg_t):
    """Circular feed: prawn meal and greenhouse waste to the fish; fish by-product meal to the prawns; local crops to both."""
    fish = seafood_t * AF["finfish_share"]; prawn = seafood_t * AF["prawn_share"]
    feed_fish = fish * AF["fcr_fish"]; feed_prawn = prawn * AF["fcr_prawn"]
    fish_meal = fish * AF["fish_byproduct_share"] * AF["fish_meal_yield"]
    prawn_meal = prawn * AF["prawn_byproduct_share"] * AF["prawn_meal_yield"]
    gh_waste = veg_t * AF["greenhouse_waste_share"]
    greens_direct = min(gh_waste * 0.5, fish * 0.25 * AF["tilapia_direct_greens_t_per_t"] * 10)    # tilapia browse fresh greens
    bsf_meal = (gh_waste - greens_direct) * AF["bsf_yield_wet"] * AF["bsf_meal_dm"]
    to_prawn_marine = min(fish_meal, feed_prawn * AF["prawn_feed_marine_share"])
    fish_meal_to_fish = fish_meal - to_prawn_marine
    local_plant_fish = feed_fish * AF["local_plant_share_fish"]; local_plant_prawn = feed_prawn * AF["local_plant_share_prawn"]
    local_fish = prawn_meal + fish_meal_to_fish + bsf_meal + greens_direct * 0.15 + local_plant_fish    # greens on a dry-matter basis
    local_prawn = to_prawn_marine + local_plant_prawn
    local_fish = min(local_fish, feed_fish); local_prawn = min(local_prawn, feed_prawn)
    imported = feed_fish + feed_prawn - local_fish - local_prawn
    ef = AF
    local_ef_t = ((prawn_meal + fish_meal) * ef["local_meal_kg_co2e_kg"] + bsf_meal * ef["bsf_kg_co2e_kg"]
                  + (local_plant_fish + local_plant_prawn) * ef["local_plant_kg_co2e_kg"])
    credit_t = (local_fish + local_prawn) * ef["imported_feed_kg_co2e_kg"] - local_ef_t
    n_in = (feed_fish + feed_prawn) * ef["feed_n_share"]
    n_dissolved = n_in * (1 - ef["n_retained"]) * ef["n_dissolved_share"]
    return dict(finfish_t=fish, prawn_t=prawn, feed_fish_t=feed_fish, feed_prawn_t=feed_prawn, fish_meal_t=fish_meal, prawn_meal_t=prawn_meal,
                greenhouse_waste_t=gh_waste, greens_direct_t=greens_direct, bsf_meal_t=bsf_meal, local_plant_t=local_plant_fish + local_plant_prawn,
                local_share_fish=local_fish / feed_fish, local_share_prawn=local_prawn / feed_prawn,
                local_share_total=(local_fish + local_prawn) / (feed_fish + feed_prawn), imported_feed_t=imported,
                credit_t=credit_t, n_feed_t=n_in, n_dissolved_t=n_dissolved,
                seaweed_capacity_t_dw=n_dissolved / LV["asp_n_share_dw"])


# ----------------------------------------------------------------------------------------------- hourly heat
def node_demands(T, comm, herd_scope="catchment"):
    H["ua_kw_per_k"] = calibrate_ua(T)
    pop_total = sum(c["population"] for c in comm.values())
    F = P.FOOD
    veg_t = pop_total * F["veg_kg_per_resident"] / 1000; sea_t = pop_total * F["seafood_kg_live_per_resident"] / 1000
    gh_ha = veg_t / (F["greenhouse_kg_m2"] * 10)
    dairy, beef = herds(herd_scope)
    asp_t = asparagopsis_need_t(dairy, beef)
    asp_ha = asp_t * 1e6 / (LV["asp_productivity_g_m2_day"] * 365) / 1e4
    ch4 = (dairy * LV["biogas_m3_ch4"]["dairy"] + beef * LV["biogas_m3_ch4"]["beef"] + LV["food_waste_t"] * LV["food_waste_m3_ch4_t"]
           + LV["crop_residue_t"] * LV["crop_residue_m3_ch4_t"])
    digester_mwh = ch4 * LV["ch4_mj_m3"] / 3600 * 0.20
    dig_nodes = ["bellingham", "haydon_bridge", "corbridge"]
    sp_loop, sp_el = loop_share(H["space_hp_lift_share"])
    hw_lift = (H["dhw_c"] - H["loop_c"]) / (H["dhw_c"] - H["mains_c"])
    hw_loop, hw_el = loop_share(hw_lift)
    out = {}
    for n in P.NODES:
        t = T[n]; c = comm[n]; share = c["population"] / pop_total
        hh = c["population"] / H["persons_per_household"]; conn = hh * H["connected_share"]
        space = conn * H["ua_kw_per_k"] * np.maximum(0, H["base_c"] - t) / 1000
        hot = np.full_like(t, conn * (dhw_kwh_per_household() + H["washing_mwh_hh"] * 1000) / 1000 / 8760)
        gprof = np.maximum(0, 18.0 - t) + 2.0
        gh = gh_ha * share * H["greenhouse_mwh_per_ha"] * gprof / gprof.sum(axis=1, keepdims=True)
        sprof = np.maximum(0, 22.0 - t) + 1.0
        sw = asp_ha * share * H["seaweed_mwh_per_ha"] * sprof / sprof.sum(axis=1, keepdims=True)
        ras = np.full_like(t, sea_t * share * H["ras_mwh_per_t"] / 8760)
        dig = np.full_like(t, digester_mwh / len(dig_nodes) / 8760 if n in dig_nodes else 0.0)
        out[n] = dict(space=space, hot=hot, home_loop=space * sp_loop + hot * hw_loop, home_el=space * sp_el + hot * hw_el,
                      greenhouse=gh, seaweed=sw, ras=ras, digester=dig, connected_households=conn, households=hh, it_mw=c["it_mw"])
    facts = dict(ua_kw_per_k=H["ua_kw_per_k"], population=pop_total, greenhouse_ha=gh_ha, veg_t=veg_t, seafood_t=sea_t, dairy=dairy, beef=beef,
                 asparagopsis_t_dw=asp_t, asparagopsis_ha=asp_ha, biogas_ch4_m3=ch4, digester_heat_mwh=digester_mwh,
                 hw_lift_share=hw_lift, washing_mwh_hh=H["washing_mwh_hh"])
    return out, facts


def run(T, comm, connected_share=None, drying_scale=1.0, continuous=False, herd_scope="catchment"):
    keep = H["connected_share"]
    if connected_share is not None:
        H["connected_share"] = connected_share
    dem, facts = node_demands(T, comm, herd_scope)
    H["connected_share"] = keep
    months = months_of_year(); ny = next(iter(T.values())).shape[0]
    st = {}
    for n in P.NODES:
        d = dem[n]
        avail = d["it_mw"] * P.NETWORK["it_utilisation"] * H["recoverable_share_it"] * (1 - H["network_loss"])
        rem = np.full_like(d["space"], avail)
        served = {}
        for k in ("home_loop", "greenhouse", "ras", "seaweed", "digester"):
            s_ = np.minimum(rem, d[k]); rem = rem - s_; served[k] = s_
        st[n] = dict(rem=rem, served=served, avail=avail, d=d, dry=np.zeros_like(rem))
    order = sorted(P.DRY_CONTRACTS, key=lambda k: P.DRY_CONTRACTS[k]["months"] is None)
    contract_served = {k: 0.0 for k in P.DRY_CONTRACTS}
    contracts = [(k, P.DRY_CONTRACTS[k]) for k in order]
    if continuous:          # one year-round stockpiled contract per node sized to that node's mean residual heat
        for n in P.NODES:
            contracts.append((f"Continuous contract at {P.NODE_LABEL[n]}", dict(water_t=st[n]["rem"].mean() * 8760 / 1.3 * 1.0, kwh_per_kg=1.3,
                                                                                 months=None, nodes=[n], fuel="oil", cap_factor=3.0)))
            contract_served[contracts[-1][0]] = 0.0
    for k, c in contracts:
        heat = c["water_t"] * c["kwh_per_kg"] * (drying_scale if not k.startswith("Continuous") else 1.0)
        mask = np.ones(8760, bool) if c["months"] is None else np.isin(months, list(c["months"]))
        for n in c["nodes"]:
            target = heat / len(c["nodes"]); cap = target / mask.sum() * c.get("cap_factor", 1.5)
            rem = st[n]["rem"]
            s_ = np.where(mask, np.minimum(rem, cap), 0.0)
            s_ = np.diff(np.minimum(np.cumsum(s_, axis=1), target), axis=1, prepend=0.0)
            st[n]["rem"] = rem - s_; st[n]["dry"] += s_; contract_served[k] += s_.sum() / ny
    q95_bywell = P.RIVERS["Tyne"]["q95"] * RHO_CP / 1000; q95_haydon = P.RIVERS["South Tyne"]["q95"] * RHO_CP / 1000
    mean_bywell = P.RIVERS["Tyne"]["mean"] * RHO_CP / 1000
    rem_all = np.stack([st[n]["rem"] for n in P.NODES]); total_rem = rem_all.sum(0)
    hb = P.NODES.index("haydon_bridge")
    RR = P.RIVER_RULE
    lim = np.where(np.isin(months, RR["summer_months"]), RR["summer_dT_limit_k"], RR["dT_limit_k"])     # K, by hour
    river = np.zeros_like(rem_all)
    river[hb] = np.minimum(rem_all[hb], q95_haydon * lim)
    main = [P.NODES.index(n) for n in P.NODES if n not in RR["no_discharge_nodes"] and n != "haydon_bridge"]
    main_rem = rem_all[main].sum(0)
    share = np.where(main_rem > 0, np.minimum(1.0, np.maximum(q95_bywell * lim - river[hb], 0.0) / np.maximum(main_rem, 1e-9)), 0.0)
    for i in main:
        river[i] = rem_all[i] * share
    dry = rem_all - river
    rows = []; monthly = np.zeros((12, 3))
    for i, n in enumerate(P.NODES):
        s = st[n]; d = s["d"]; sv = s["served"]
        r = dict(node=P.NODE_LABEL[n], it_mw=d["it_mw"], recoverable_gwh=s["avail"] * 8.76,
                 homes_demand_gwh=d["home_loop"].sum() / ny / 1e3, homes_gwh=sv["home_loop"].sum() / ny / 1e3,
                 homes_coverage=sv["home_loop"].sum() / max(d["home_loop"].sum(), 1e-9),
                 greenhouse_gwh=sv["greenhouse"].sum() / ny / 1e3, ras_gwh=sv["ras"].sum() / ny / 1e3, seaweed_gwh=sv["seaweed"].sum() / ny / 1e3,
                 digester_gwh=sv["digester"].sum() / ny / 1e3, drying_gwh=s["dry"].sum() / ny / 1e3,
                 river_gwh=river[i].sum() / ny / 1e3, dry_cooler_gwh=dry[i].sum() / ny / 1e3, peak_rejected_mw=float(rem_all[i].max()),
                 connected_households=d["connected_households"], households=d["households"],
                 heat_per_household_mwh=(d["space"].sum() + d["hot"].sum()) / ny / max(d["connected_households"], 1),
                 home_hp_el_gwh=d["home_el"].sum() / ny / 1e3)
        r["used_share"] = (r["homes_gwh"] + r["greenhouse_gwh"] + r["ras_gwh"] + r["seaweed_gwh"] + r["digester_gwh"] + r["drying_gwh"]) / r["recoverable_gwh"]
        rows.append(r)
        used = sum(sv.values())
        for m in range(12):
            mm = months == m + 1
            monthly[m, 0] += used[:, mm].sum() / ny; monthly[m, 1] += s["dry"][:, mm].sum() / ny; monthly[m, 2] += rem_all[i][:, mm].sum() / ny
    g = lambda k: sum(r[k] for r in rows)
    th = {k: g(k) for k in ("recoverable_gwh", "homes_gwh", "homes_demand_gwh", "greenhouse_gwh", "ras_gwh", "seaweed_gwh", "digester_gwh",
                            "drying_gwh", "river_gwh", "dry_cooler_gwh", "home_hp_el_gwh")}
    th["it_heat_gwh"] = P.NETWORK["it_mw"] * P.NETWORK["it_utilisation"] * 8.76
    th["used_gwh"] = sum(th[k] for k in ("homes_gwh", "greenhouse_gwh", "ras_gwh", "seaweed_gwh", "digester_gwh", "drying_gwh"))
    th["used_share_of_recoverable"] = th["used_gwh"] / th["recoverable_gwh"]
    th["used_share_of_it_heat"] = th["used_gwh"] / th["it_heat_gwh"]
    facility_gwh = P.NETWORK["it_mw"] * P.NETWORK["it_utilisation"] * P.NETWORK["pue"] * 8.76
    th["erf"] = th["used_gwh"] / facility_gwh
    th["useful_energy_efficiency"] = (th["it_heat_gwh"] + th["used_gwh"]) / facility_gwh     # IT work + reused heat, per unit of facility electricity
    th["used_share_without_drying"] = (th["used_gwh"] - th["drying_gwh"]) / th["recoverable_gwh"]
    rivers = dict(q95_bywell_mw_per_k=q95_bywell, q95_haydon_mw_per_k=q95_haydon, peak_total_rejected_mw=float(total_rem.max()),
                  dT_at_q95_if_all_to_river=float(total_rem.max()) / q95_bywell, dT_at_mean_flow=float(total_rem.max()) / mean_bywell,
                  dry_cooler_peak_total_mw=float(dry.sum(0).max()), river_share_of_rejected=float(river.sum() / max(rem_all.sum(), 1e-9)),
                  dry_cooler_peak_by_node_mw={P.NODE_LABEL[n]: float(dry[i].max()) for i, n in enumerate(P.NODES)},
                  river_peak_by_node_mw={P.NODE_LABEL[n]: float(river[i].max()) for i, n in enumerate(P.NODES)},
                  peak_dT_haydon_k=float(river[hb].max() / q95_haydon), peak_dT_bywell_k=float(river.sum(0).max() / q95_bywell))
    return dict(nodes=rows, thermal=th, contracts_served_gwh={k: v / 1e3 for k, v in contract_served.items()},
                monthly_gwh=(monthly / 1e3).tolist(), rivers=rivers, facts=facts)


# ----------------------------------------------------------------------------------------------- ledger and baselines
def ledger(heat, grid_g, dg_g, feed, full=True, asparagopsis=True, biogas_to_block_mwh=0.0):
    EF = P.FUEL_EF; M = P.MOBILITY
    adopt = 1.0 if full else 0.5
    homes_t = 0.0; washing_t = 0.0
    for r in heat["nodes"]:
        n = [k for k, v in P.NODE_LABEL.items() if v == r["node"]][0]
        off = H["off_gas_share"][n]; mix = H["off_gas_fuel"]
        hh = r["connected_households"]
        heat_mwh = r["heat_per_household_mwh"] * hh                 # delivered space heat + hot water + washing
        wash_mwh = hh * H["washing_mwh_hh"]
        space_dhw = heat_mwh - wash_mwh
        fuel_t = (1 - off) * EF["gas"] + off * (mix["heating_oil"] * EF["heating_oil"] + mix["lpg"] * EF["lpg"])
        homes_t += space_dhw / H["boiler_eff"] * fuel_t + space_dhw * off * mix["electric"] * grid_g / 1e3
        washing_t += wash_mwh * grid_g / 1e3                         # appliances otherwise heat their own water electrically
        homes_t -= r["home_hp_el_gwh"] * 1e3 * dg_g / 1e3
    ef_fuel = dict(oil=EF["heating_oil"], gas=EF["gas"], biomass=0.0)
    dry_t = sum(v * 1e3 / P.DRYING["dryer_eff"] * ef_fuel[P.DRY_CONTRACTS[k]["fuel"]] for k, v in heat["contracts_served_gwh"].items()
                if k in P.DRY_CONTRACTS)
    dairy, beef = heat["facts"]["dairy"], heat["facts"]["beef"]
    enteric_t = (dairy * LV["enteric_kg_ch4"]["dairy"] + beef * LV["enteric_kg_ch4"]["beef"]) / 1000
    asp_ch4 = ((dairy * LV["enteric_kg_ch4"]["dairy"] * LV["asp_coverage"]["dairy"] * LV["asp_reduction"]["dairy"]
                + beef * LV["enteric_kg_ch4"]["beef"] * LV["asp_coverage"]["beef"] * LV["asp_reduction"]["beef"]) / 1000) if asparagopsis else 0.0
    manure_ch4 = (dairy * LV["manure_kg_ch4"]["dairy"] + beef * LV["manure_kg_ch4"]["beef"]) * LV["ad_storage_reduction"] / 1000
    ch4_kg = heat["facts"]["biogas_ch4_m3"] * 0.717
    leak_ch4 = ch4_kg * (LV["fugitive_baseline"] - LV["fugitive_with_sensors"]) / 1000
    biomethane_mwh = heat["facts"]["biogas_ch4_m3"] * LV["ch4_mj_m3"] / 3600 - biogas_to_block_mwh
    farm_l = farm_fuel_l(dairy)
    from power_247 import vehicles
    V = vehicles()
    elec_share = 1 - M["phev_share"] * (1 - M["phev_electric_share"])
    displaced_km = V["existing"] * M["km_per_ev"] * elec_share
    new_petrol_km = V["new_for_zero_car"] * M["km_per_ev"] * M["phev_share"] * (1 - M["phev_electric_share"])
    charge_kwh = V["total"] * M["km_per_ev"] * elec_share * M["kwh_per_100km"] / 100
    ev_t = (displaced_km - new_petrol_km) * EF["petrol_car_kg_km"] / 1000 - charge_kwh * dg_g / 1e6
    hvo_t = heat["facts"]["population"] * M["renewable_fuel_l_per_resident"] * M["diesel_lifecycle_kg_l"] * M["hvo_reduction"] / 1000
    g = LV["gwp_ch4"]
    rows = {
        "Home heating and hot water through district loops and home heat pumps": homes_t * adopt,
        "Hot-fill washing and cleaning water": washing_t * adopt,
        "Drying contracts (fossil-fired drying displaced)": dry_t * adopt,
        "Free red seaweed (Asparagopsis) for dairy and beef cattle": asp_ch4 * g * adopt,
        "Manure and crop residues to digesters (storage methane avoided)": manure_ch4 * g * adopt,
        "Methane-leak detection on digesters and upgraders": leak_ch4 * g * adopt,
        "Biomethane displacing natural gas": biomethane_mwh * EF["gas"] * adopt,
        "Farm red diesel replaced by subsidised HVO (all farms)": farm_l * M["diesel_lifecycle_kg_l"] * M["hvo_reduction"] / 1000 * adopt,
        "Household vehicles replaced by battery-electric and plug-in hybrid vehicles": ev_t,
        "Renewable fuel for residents' remaining vehicles (HVO)": hvo_t,
        "Circular aquafeed replacing imported feed": feed["credit_t"],
    }
    # baselines
    pop = heat["facts"]["population"]
    uk_pc = P.UK_GHG["territorial_mt_2024"] / P.UK_GHG["population_m_2024"]
    homes_base = 0.0
    for r in heat["nodes"]:
        n = [k for k, v in P.NODE_LABEL.items() if v == r["node"]][0]
        off = H["off_gas_share"][n]; mix = H["off_gas_fuel"]
        sd = (r["heat_per_household_mwh"] - H["washing_mwh_hh"]) * r["households"]
        homes_base += sd / H["boiler_eff"] * ((1 - off) * EF["gas"] + off * (mix["heating_oil"] * EF["heating_oil"] + mix["lpg"] * EF["lpg"])) \
            + sd * off * mix["electric"] * grid_g / 1e3 + r["households"] * H["washing_mwh_hh"] * grid_g / 1e3
    vehicles_base = V["existing"] * M["km_per_ev"] * EF["petrol_car_kg_km"] / 1000
    cattle_base = (enteric_t + (dairy * LV["manure_kg_ch4"]["dairy"] + beef * LV["manure_kg_ch4"]["beef"]) / 1000) * g \
        + farm_l * M["diesel_lifecycle_kg_l"] / 1000
    addressed = homes_base + vehicles_base + cattle_base + pop * M["renewable_fuel_l_per_resident"] * M["diesel_lifecycle_kg_l"] / 1000
    total = sum(rows.values())
    territorial = pop * uk_pc + cattle_base
    return dict(rows=rows, total_t=total, enteric_t_ch4=enteric_t, asp_ch4_t=asp_ch4, asp_enteric_cut_share=asp_ch4 / enteric_t if enteric_t else 0,
                leak_ch4_t=leak_ch4, biomethane_gwh=biomethane_mwh / 1e3, farm_hvo_ml=farm_l / 1e6, hvo_ml=pop * M["renewable_fuel_l_per_resident"] / 1e6,
                baselines=dict(uk_per_capita_t=uk_pc, residents_territorial_t=pop * uk_pc, cattle_t=cattle_base, homes_t=homes_base,
                               vehicles_t=vehicles_base, addressed_sectors_t=addressed, residents_plus_cattle_t=territorial),
                percent=dict(of_addressed_sectors=total / addressed, of_residents_plus_cattle=total / territorial,
                             of_residents_territorial=total / (pop * uk_pc)))


def farm_fuel_l(dairy):
    """Red diesel used by all farms in the catchment (scaled with the herd scope: catchment or whole North East)."""
    FF = P.FARM_FUEL
    ha = FF["ne_farmed_ha"] * dairy / LV["ne_dairy"]
    return ha * sum(FF["area_share"][k] * FF["red_l_per_ha"][k] for k in FF["area_share"])


def farm_fuel_subsidy_gbp_l():
    return P.BACKUP["hvo_gbp_l"] - P.FARM_FUEL["red_diesel_gbp_l"]


def programme_costs(heat, feed):
    F = P.FOOD; M = P.MOBILITY; f = heat["facts"]
    hh = sum(r["connected_households"] for r in heat["nodes"])
    from power_247 import vehicles
    V = vehicles(); veh_price = V["bev"] * M["bev_gbp"] + V["phev"] * M["phev_gbp"]
    biogas_gj = f["biogas_ch4_m3"] * LV["ch4_mj_m3"] / 1000
    capex = dict(district_heat=hh * H["dh_capex_gbp_household"], home_heat_pumps=hh * 4000.0,
                 greenhouses=f["greenhouse_ha"] * F["greenhouse_capex_gbp_ha"], aquaculture=f["seafood_t"] * F["ras_capex_gbp_annual_t"],
                 seaweed_tanks=f["asparagopsis_ha"] * 1e4 * LV["asp_capex_gbp_m2"], feed_mill_and_insects=3.0e6,
                 digesters=biogas_gj * LV["ad_capex_gbp_per_gj_yr"], leak_detection=LV["sensor_sites"] * LV["sensor_capex_gbp"])
    dry_kw = sum(v * 1e3 / 8760 * 1.5 * 1000 for k, v in heat["contracts_served_gwh"].items())
    capex["drying_hubs"] = dry_kw * (P.DRYING["capex_dryer_gbp_kw"] + P.DRYING["capex_pipe_gbp_kw"])
    opex = dict(district_heat=capex["district_heat"] * H["dh_om_frac"], home_heat_pumps=hh * 100.0,
                food_nonlabour=f["veg_t"] * 1000 * F["veg_nonlabour_gbp_kg"] + f["seafood_t"] * 1000 * F["seafood_nonlabour_gbp_kg"] * 0.8,
                ev_om=V["total"] * M["ev_om_gbp"], renewable_fuel_subsidy=f["population"] * M["renewable_fuel_l_per_resident"] * M["renewable_fuel_subsidy_gbp_l"],
                farm_hvo_subsidy=farm_fuel_l(f["dairy"]) * farm_fuel_subsidy_gbp_l(),
                seaweed=capex["seaweed_tanks"] * LV["asp_om_frac"], digesters=capex["digesters"] * LV["ad_om_frac"],
                leak_detection=LV["sensor_sites"] * LV["sensor_om_gbp"],
                drying=capex["drying_hubs"] * P.DRYING["om_frac"] + sum(c["water_t"] for c in P.DRY_CONTRACTS.values()) * P.DRYING["handling_gbp_t_water"])
    price = dict(oil=P.DRYING["oil_gbp_mwh"], gas=P.DRYING["gas_gbp_mwh"], biomass=P.DRYING["biomass_gbp_mwh"])
    dry_rev = sum(v * 1e3 / P.DRYING["dryer_eff"] * price[P.DRY_CONTRACTS[k]["fuel"]] * (1 - P.DRYING["discount_to_fossil"])
                  for k, v in heat["contracts_served_gwh"].items() if k in P.DRY_CONTRACTS and not P.DRY_CONTRACTS[k].get("barter"))
    biomethane_rev = f["biogas_ch4_m3"] * LV["ch4_mj_m3"] / 3600 * LV["biomethane_gbp_mwh"]
    r_, n_ = M["finance_rate"], M["finance_years"]
    pay = veh_price * r_ * (1 + r_) ** n_ / ((1 + r_) ** n_ - 1)
    return dict(capex=capex, capex_total=sum(capex.values()), opex=opex, opex_total=sum(opex.values()),
                revenue=dict(drying=dry_rev, biomethane=biomethane_rev), revenue_total=dry_rev + biomethane_rev, connected_households=hh,
                vehicles=dict(V, fleet_value_gbp=veh_price, annual_finance_payment_gbp=pay, finance_years=n_, finance_rate=r_, life=M["vehicle_life"],
                              payment_years=[y for y in range(1, P.COSTS["horizon"] + 1) if (y - 1) % M["vehicle_life"] < n_]))


def jobs(heat, feed, block=True):
    J = P.JOBS; f = heat["facts"]
    from power_247 import vehicles
    V = vehicles()
    j = {"IT/data-centre operations": int(np.ceil(P.NETWORK["it_mw"] * J["it_fte_per_mw"])),
         "Greenhouse horticulture": int(np.ceil(f["greenhouse_ha"] * J["greenhouse_fte_per_ha"])),
         "Fish and prawn farming": int(np.ceil(f["seafood_t"] * J["aquaculture_fte_per_t"])),
         "Seafood processing and packing": int(np.ceil(f["seafood_t"] * J["processing_fte_per_t"])),
         "Red-seaweed cultivation and distribution": int(np.ceil(f["asparagopsis_ha"] * J["seaweed_fte_per_ha"])),
         "Feed mill and insect (black soldier fly) unit": J["feed_mill_fte"],
         "District heat and home heat-pump service": int(np.ceil(heat_households(heat) / J["dh_households_per_fte"])),
         "Drying hubs": int(np.ceil(heat["thermal"]["drying_gwh"] / 10 * J["drying_fte_per_10gwh"])),
         "Digesters and methane-leak detection": J["digester_fte"] + J["leak_detection_fte"],
         "Vehicle fleet service and charging": int(np.ceil(V["total"] / J["vehicles_per_fte"])) + J["vehicle_fte"],
         "Renewables, battery and standby generation": int(np.ceil((250 + 1200) * J["renewable_fte_per_mw"] * 0.5)) + J["block_fte"],
         "Logistics and food distribution": J["logistics_fte"], "Programme administration and audit": J["admin_fte"]}
    fte = sum(j.values())
    return dict(by_sector=j, total=fte, cost_gbp=fte * J["wage_gbp"] * (1 + J["oncost"]))


def heat_households(heat):
    return sum(r["connected_households"] for r in heat["nodes"])


def main():
    d = json.load(open(P.OUT / "design.json")); pw = json.load(open(P.OUT / "power_247.json"))
    comm = load_communities(); T = temps()
    grid_g = float(np.mean(list(pw["gb_intensity_mean_by_year"].values())))
    s = d["selected"]; dg_g = (s["import_t"] + s["lca_t"]) / (d["annual_load_gwh"] * 1e3) * 1e3
    heat = run(T, comm)
    feed = feed_loop(heat["facts"]["seafood_t"], heat["facts"]["veg_t"])
    led_full = ledger(heat, grid_g, dg_g, feed, True, True)
    led_noasp = ledger(heat, grid_g, dg_g, feed, True, False)
    led_lim = ledger(heat, grid_g, dg_g, feed, False, False)
    heat_ne = run(T, comm, herd_scope="north_east")
    led_ne = ledger(heat_ne, grid_g, dg_g, feed, True, True)
    costs = programme_costs(heat, feed); jb = jobs(heat, feed)
    w_rows = {k: v * P.TIER_WEIGHT[P.COMMUNITY_TIER[k]] for k, v in led_full["rows"].items()}
    led_w = dict(rows=w_rows, total_t=sum(w_rows.values()),
                 tier_t={t: sum(v for k, v in led_full["rows"].items() if P.COMMUNITY_TIER[k] == t) for t in "ABC"},
                 tier_weighted_t={t: sum(v for k, v in w_rows.items() if P.COMMUNITY_TIER[k] == t) for t in "ABC"})
    led_w["percent"] = dict(of_addressed_sectors=led_w["total_t"] / led_full["baselines"]["addressed_sectors_t"],
                            of_residents_plus_cattle=led_w["total_t"] / led_full["baselines"]["residents_plus_cattle_t"])
    sens = {}
    for name, kw in (("connected 80%", dict(connected_share=0.80)), ("drying x2", dict(drying_scale=2.0)),
                     ("continuous drying contracts at every node", dict(continuous=True)), ("seaweed for the whole North East herd", dict(herd_scope="north_east"))):
        h2 = heat_ne if name.startswith("seaweed") else run(T, comm, **kw)
        sens[name] = {k: h2["thermal"][k] for k in ("used_share_of_recoverable", "used_share_of_it_heat", "erf", "useful_energy_efficiency",
                                                     "homes_gwh", "drying_gwh", "seaweed_gwh", "river_gwh", "dry_cooler_gwh")}
        if name.startswith("continuous"):
            sens[name]["continuous_contracts_gwh"] = sum(v for k, v in h2["contracts_served_gwh"].items() if k.startswith("Continuous"))
            sens[name]["dry_cooler_peak_mw"] = h2["rivers"]["dry_cooler_peak_total_mw"]
            sens[name]["fossil_drying_displaced_t"] = sum(v * 1e3 / P.DRYING["dryer_eff"] * P.FUEL_EF["heating_oil"]
                                                          for k, v in h2["contracts_served_gwh"].items() if k.startswith("Continuous"))
    out = dict(heat=heat, feed=feed, ledger_full=led_full, ledger_no_asparagopsis=led_noasp, ledger_limited=led_lim, ledger_weighted=led_w,
               ledger_north_east_seaweed=led_ne, heat_north_east=dict(facts=heat_ne["facts"], thermal=heat_ne["thermal"]),
               programme=costs, jobs=jb, sensitivities=sens, grid_mean_g_kwh=grid_g, dg_supply_g_kwh=dg_g)
    json.dump(out, open(P.OUT / "heat_community.json", "w"), indent=2, default=float)
    print({k: round(v, 3) for k, v in heat["thermal"].items()})
    print("facts", {k: round(v, 3) for k, v in heat["facts"].items()})
    print("feed", {k: round(v, 3) for k, v in feed.items()})
    print("rivers", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in heat["rivers"].items()})
    for nm, L in (("full", led_full), ("no asp", led_noasp), ("limited", led_lim), ("NE seaweed", led_ne)):
        print(nm, round(L["total_t"]), {k: round(v, 3) for k, v in L["percent"].items()}, "asp cut", round(L["asp_enteric_cut_share"], 3))
    for k, v in led_full["rows"].items():
        print(f"  {v:10.0f}  {k}")
    print("baselines", {k: round(v) for k, v in led_full["baselines"].items()})
    print("capex £m", {k: round(v / 1e6, 1) for k, v in costs["capex"].items()}, round(costs["capex_total"] / 1e6, 1))
    print("opex £m", round(costs["opex_total"] / 1e6, 1), "rev £m", round(costs["revenue_total"] / 1e6, 2), "veh pay", round(costs["vehicles"]["annual_finance_payment_gbp"] / 1e6, 1))
    print("jobs", jb["total"], jb["by_sector"])
    print("sens", json.dumps(sens, default=float)[:1500])


P_SELECTED_CFE = 1.0

if __name__ == "__main__":
    main()
