"""Declared screening assumptions for Digital Gardens of the North Tyne Valley versus QTS Cambois and Stargate UK.

Every number used by the model is defined here with its source or its status as an assumption. Money is real GBP at
2024 prices (the price base of the CfD Allocation Round 7 strike prices) unless marked USD; GPU economics are in USD and
converted at GBP_PER_USD. Historical wholesale prices (2018-2025) are nominal outturn and are used as observed.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "DATA"
OUT = HERE / "OUTPUT"
WX_DIR = DATA / "Digital_Gardens_UK_ERA5_historical"      # unpacked output of digital_gardens_uk_era5.py
GRID_DIR = DATA / "Digital_Gardens_UK_GRID"                 # unpacked output of digital_gardens_uk_grid.py

GBP_PER_USD = 0.78
WEATHER_YEARS = list(range(2010, 2026))
GRID_YEARS = list(range(2018, 2026))           # years with regional carbon intensity and half-hourly prices

# ----------------------------------------------------------------------------------------------- network
NODES = ["falstone", "bellingham", "wark", "barrasford", "chollerford", "haydon_bridge", "hexham", "corbridge"]
NODE_LABEL = {"falstone": "Falstone", "bellingham": "Bellingham", "wark": "Wark", "barrasford": "Barrasford",
              "chollerford": "Chollerford", "haydon_bridge": "Haydon Bridge", "hexham": "Hexham", "corbridge": "Corbridge"}
NETWORK = dict(
    it_mw=93.50836,             # Digital Gardens website archive, 4.46 kW of IT per resident x 20,966 residents [1]
    kw_it_per_resident=4.46,
    it_utilisation=0.90,        # average IT draw as a share of installed IT (assumption, as in the website model)
    pue=1.15,                   # liquid-cooled halls with heat-recovery pumping (website value)
)

# ----------------------------------------------------------------------------------------------- comparators
COMPARATORS = {
    "QTS Cambois": dict(
        it_mw=720.0,            # ten buildings of 72 MW of IT (Corgan project page); 720 MW campus (QTS/NCC)
        pue=1.20,               # assumption for closed-loop free-cooling chillers in Northumberland; 1.15-1.30 tested
        utilisation=0.90,
        heat_reuse_mw=0.0,      # QTS will "explore the viability" of a district heating network with NCC; nothing committed
        cooling_water_m3_yr=0.0,  # waterless closed-loop free-cooling chillers (QTS; DCD)
        operational_jobs=400, construction_jobs=1200,
        aigz_discount_gbp_mwh=14.0,   # North East AI Growth Zone discount, up to GBP14/MWh from April 2027, review 2030
        status="outline permission March 2025; first two buildings approved 2 December 2025; enabling works under way",
    ),
    "Stargate UK (Cobalt Park)": dict(
        gpus_initial=8000, gpus_potential=31000,   # OpenAI, 16 September 2025
        pue=1.20, utilisation=0.90, heat_reuse_mw=0.0, cooling_water_m3_yr=None,
        aigz_discount_gbp_mwh=14.0,
        status="paused by OpenAI in April 2026 citing energy costs and regulation; Cobalt Park hosts about 35 MW today",
    ),
}

# ----------------------------------------------------------------------------------------------- weather and power
WIND_SITES = ["kielder_upland_wind_proxy", "wark_forest_wind_proxy", "ridsdale_ray_wind_proxy",
              "northumberland_coast_wind_proxy"]
POWER = dict(
    # generic 4-5 MW turbine at 100 m; piecewise anchors declared in power_247.py,
    # with 12% aggregate losses. Baseline scaled to 30% CF; raw-ERA5 separate.
    cut_in=3.0, rated=12.0, cut_out=25.0,
    wind_losses_factor=0.88,     # 12% combined losses; illustrative generic turbine, not measured manufacturer curve
    wind_cf_central=0.30,       # between the GB onshore fleet 2020-24 load factor (25.3%) and DESNZ new-build 36%
    wind_cf_tests=[0.253, 0.30, 0.36],
    pv_performance_ratio=0.82, pv_temp_coeff=-0.004, pv_noct_rise=25.0,   # cell temperature = air + 25 C x GHI/800
    battery_rt=0.88,            # 0.94 charge x 0.94 discharge (as in the BC study)
    battery_hours=4.0,
)
COSTS = dict(
    ppa_wind_gbp_mwh=72.24,     # CfD AR7 onshore wind clearing strike price, 2024 prices (DESNZ, Feb 2026)
    ppa_solar_gbp_mwh=65.23,    # CfD AR7 solar PV clearing strike price, 2024 prices
    battery_capex_gbp_kwh=250.0,    # 4-hour lithium-ion system, installed (assumption)
    battery_fom_frac=0.015, battery_life=15, battery_replacement_frac=0.60,
    procurement_limit=1.25,     # used only for the fossil-free-first comparison case
    battery_max_mwh=400.0,      # 'reasonably sized' battery: about four hours of network load
    self_supply_target=0.80,    # least-cost portfolio reaching this hourly self-supply share is the design case
    sellback_limit=2.0,         # contracted output up to 2x annual consumption: about half is sold back to the grid
    export_credit='full',       # surplus sold at the hourly wholesale price (capped and zero credit tested)
    rego_gbp_mwh=5.0,           # annual certificate matching for the comparator (assumption)
    # non-commodity charges on grid-delivered electricity, identical for all designs except the AIGZ discount
    non_commodity_gbp_mwh=dict(tnuos=25.7, bsuos=13.74, ro=30.0, cfd=5.0, fit=4.0, cm=4.0, ccl=8.0, duos_ehv=5.0),
    discount_rate=0.06, finance_years=20, horizon=25,
    normalised_wholesale_mean=None,   # set in power_247.py to the 2025 observed mean for the 'normalised' price case
)

# ----------------------------------------------------------------------------------------------- renewable-fuel backup
BACKUP = dict(
    # combined-cycle block of two SGT-800-class gas turbines (HVO service demonstrated: Stockholm Exergi 2023, Uniper 2021)
    mw=110.0,                   # covers the ~99-120 MW network load with margin
    efficiency=0.52,            # combined cycle on liquid fuel (aeroderivative/industrial CC 52-56% on gas; liquid derated)
    capex_gbp_kw=1300.0, fom_gbp_kw_yr=20.0, vom_gbp_mwh=5.0, life=25,
    hvo_lhv_mj_l=34.4,          # 44.0 MJ/kg x 0.78 kg/L
    hvo_gbp_l=1.25,             # UK bulk HVO GBP1.20-1.30/L (supplier ranges, 2025-26)
    b100_gbp_l=1.15, b100_lhv_mj_l=33.0,
    tank_days=14.0,             # liquid storage at full output
    trimix_trigger=0.33,        # below one third of tank capacity the block switches to tri-mix
    trimix_biogas_max_share=0.50,   # dual-fuel limit on gaseous share of fuel energy
    trimix_b100_share_of_liquid=0.30,
    biogas_buffer_days=3.0,
    tank_gbp_m3=150.0, carry_rate=0.06,
    lca_g_mj=dict(hvo=21.6, b100=21.6, biogas=10.0),   # RTFO 2024: 77% saving incl. ILUC vs 94 g/MJ fossil
    nox_kg_mwh=0.05,            # liquid-fired CC with water injection and SCR (assumption; gas-fired CC with SCR ~0.025)
    allowance_ml=[0.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0],
    test_hours_per_year=12.0,
    # islanded operation: the block (at the Hexham node) reaches the other nodes over a private 33 kV network; contracted wind
    # and solar are sleeved through the public grid and are NOT available to the nodes during a grid outage
    island_network_gbp_km=0.8e6, island_switchgear_gbp=6.0e6,   # per circuit-km of 33 kV cable; double circuits (see ISLAND)   # monthly one-hour full-load test runs; otherwise the block runs only on grid failure
)

# ----------------------------------------------------------------------------------------------- emissions
LCA = dict(wind_g_kwh=11.0, solar_g_kwh=35.0, battery_kg_per_kwh=70.0, battery_life=15)
# forward GB grid path for the comparators (location basis): observed 2025 mean, Clean Power 2030 '<50 g/kWh', CCC 2035 10 g/kWh
GRID_PATH_G_KWH = {2025: None, 2030: 50.0, 2035: 10.0}
FUEL_EF = dict(              # DESNZ GHG conversion factors (combustion, kg CO2e per kWh gross CV); upstream excluded
    gas=0.18290, heating_oil=0.24677, lpg=0.21449, petrol_car_kg_km=0.164, diesel_kg_l=2.51,
)

# ----------------------------------------------------------------------------------------------- heat
HEAT = dict(
    recoverable_share_it=0.85,  # liquid-cooled capture at 45-55 C
    network_loss=0.15,
    persons_per_household=2.36,
    connected_share=1.00,       # hot-water lines to every household in the covenant communities; 80% tested
    hp_cop=5.0,                 # small water-to-water heat pumps in each home lifting the 45-55 C loop
    space_hp_lift_share=0.15,   # share of space heat supplied as heat-pump lift (radiator temperatures above the loop)
    washing_mwh_hh=0.5,         # hot-fill washing machines, dishwashers and cleaning water at 60 C, per household per year
    ua_kw_per_k=0.20, base_c=15.5, dhw_l_person_day=50.0, dhw_c=60.0, loop_c=50.0, mains_c=8.0,
    boost_below_c=-5.0, boost_share=0.30, booster_cop=3.5,
    boiler_eff=0.85,
    off_gas_share={"falstone": 0.90, "bellingham": 0.70, "wark": 0.90, "barrasford": 0.90, "chollerford": 0.80,
                   "haydon_bridge": 0.30, "hexham": 0.10, "corbridge": 0.15},   # screening; county 30-35% off gas (CAN; NECA)
    off_gas_fuel={"heating_oil": 0.60, "electric": 0.25, "lpg": 0.15},
    greenhouse_mwh_per_ha=2400.0, ras_mwh_per_t=1.2, seaweed_mwh_per_ha=3000.0,
    dh_capex_gbp_household=15000.0, dh_om_frac=0.015, dh_life=40,
)
RIVERS = {   # receiving water for closed-loop river heat exchangers; flows from NRFA via EA gauges
    "North Tyne": dict(nodes=["falstone", "bellingham", "wark", "barrasford", "chollerford"], q95=None, mean=None,
                       note="regulated by Kielder releases; no NRFA statistics used here, so these nodes are checked at Bywell"),
    "South Tyne": dict(nodes=["haydon_bridge"], q95=2.16, mean=19.8, gauge="23004 Haydon Bridge"),
    "Tyne": dict(nodes=["hexham", "corbridge"], q95=6.12, mean=45.4, gauge="23001 Bywell (all eight nodes upstream)"),
}
DRYING = dict(
    discount_to_fossil=0.25, oil_gbp_mwh=70.0, gas_gbp_mwh=45.0, biomass_gbp_mwh=25.0, dryer_eff=0.80,
    capex_dryer_gbp_kw=350.0, capex_pipe_gbp_kw=100.0, om_frac=0.03, handling_gbp_t_water=6.0, truck_gbp_t_km=0.12,
    pipe_gbp_km=2.0e6,
)
# water_t: tonnes of water removed per year (screening); kwh_per_kg: dryer heat per kg water; months: None = year-round
# fuel: what the customer burns today; nodes: hub nodes; delivery: ('pipe', km) or ('truck', km); wet: t wet per t water
DRY_CONTRACTS = {
    "Wood-chip pre-drying for panel board (Hexham)": dict(
        water_t=100_000, kwh_per_kg=1.30, months=None, fuel="biomass", nodes=["hexham"], delivery=("pipe", 2.0), wet=2.2,
        note="low-temperature belt pre-drying of wet chips ahead of a panel plant's drum dryers; the plant's 35 MW hot-gas dryers "
             "burn its own wood residue, so no fossil credit is taken (screening; no discussions held)"),
    "Woodfuel logs and chips (Kielder and Wark forests)": dict(
        water_t=20_000, kwh_per_kg=1.35, months=None, fuel="oil", nodes=["falstone", "bellingham", "wark"], delivery=("truck", 25), wet=2.5,
        note="forest residue and roundwood fuel dried from 50% to 25% moisture"),
    "Grain drying for local farmers (bartered for manure and crop residues)": dict(
        water_t=6_000, kwh_per_kg=1.30, months=range(8, 11), fuel="oil", nodes=["corbridge", "hexham", "haydon_bridge"], delivery=("truck", 20), wet=8.3,
        barter=True, note="cereals dried 12 points in August-October; paid in manure and crop residues for the digesters"),
    "Hay, haylage, straw and farm woodchip drying (bartered)": dict(
        water_t=8_000, kwh_per_kg=1.30, months=range(5, 10), fuel="oil", nodes=["bellingham", "wark", "barrasford", "chollerford", "haydon_bridge"],
        delivery=("truck", 20), wet=4.0, barter=True, note="barn drying of forage and farm woodchip for upland livestock farms, paid in manure"),
    "Municipal biosolids": dict(
        water_t=60_000 * 25 / 1000 * (1 / 0.22 - 1 / 0.90), kwh_per_kg=1.30, months=None, fuel="gas", nodes=["hexham", "corbridge", "haydon_bridge"], delivery=("truck", 15), wet=1.32,
        note="25 kg dry solids per person per year for a 60,000-person catchment, 22% cake to 90% solids"),
    "Brewers' spent grain and food by-products": dict(
        water_t=2_500, kwh_per_kg=1.40, months=None, fuel="gas", nodes=["hexham", "corbridge"], delivery=("truck", 20), wet=1.39,
        note="local breweries and food processors"),
    "Commercial laundry (hospital, hotels, care homes)": dict(
        water_t=3_000, kwh_per_kg=1.50, months=None, fuel="gas", nodes=["hexham"], delivery=("truck", 10), wet=4.6,
        note="linen from Hexham General Hospital, hotels and care homes"),
    "Seafood by-products to feed meal": dict(
        water_t=964.436 * 0.35 * 0.65, kwh_per_kg=1.40, months=None, fuel="gas", nodes=["hexham", "corbridge"], delivery=("truck", 5), wet=1.6,
        note="processing by-products of the Digital Gardens aquaculture"),
}

# ----------------------------------------------------------------------------------------------- community programme
FOOD = dict(veg_kg_per_resident=146.0, seafood_kg_live_per_resident=46.0, greenhouse_kg_m2=26.0,
            veg_nonlabour_gbp_kg=1.4, seafood_nonlabour_gbp_kg=4.0, greenhouse_capex_gbp_ha=2.3e6, ras_capex_gbp_annual_t=30000.0,
            home_hp_el_gwh=3.0, seaweed_pumping_el_gwh=1.0,   # home heat pumps (from heat_community) and seaweed-tank circulation
            greenhouse_el_mwh_per_ha=700.0, ras_el_mwh_per_t=2.0, processing_el_gwh=2.5, seaweed_el_gwh=1.0)
MOBILITY = dict(
    # one-for-one replacement of every household car or van with a battery-electric or plug-in hybrid vehicle, and one
    # vehicle for every household without one (Census 2021 TS045, Northumberland: 19.7% none, 43.1% one, 28.1% two, 9.1% 3+)
    car_dist={0: 0.197, 1: 0.431, 2: 0.281, 3: 0.091}, three_plus_mean=3.2,
    phev_share=0.20, bev_gbp=30000.0, phev_gbp=32000.0, phev_electric_share=0.50,
    finance_years=7, finance_rate=0.065, vehicle_life=12,     # 84-month finance, the longest standard UK term
    ev_om_gbp=400.0, km_per_ev=11000.0,
    kwh_per_100km=17.0, renewable_fuel_l_per_resident=200.0, renewable_fuel_subsidy_gbp_l=0.50,
                hvo_reduction=0.75, diesel_lifecycle_kg_l=3.2)
LIVESTOCK = dict(   # North East region June Survey 2023: dairy herd 12k, beef herd 64k (Defra). Catchment share is an assumption.
    ne_dairy=12000, ne_beef=64000, catchment_share=0.20,
    enteric_kg_ch4=dict(dairy=141.0, beef=113.0), gwp_ch4=28.0,
    asp_reduction=dict(dairy=0.30, beef=0.68), asp_coverage=dict(dairy=0.90, beef=150 / 365),
    asp_capex_gbp_head=120.0, asp_om_gbp_head=60.0,
    manure_kg_ch4=dict(dairy=45.0, beef=8.0), ad_storage_reduction=0.80,
    crop_residue_t=5000.0, crop_residue_m3_ch4_t=80.0,      # crop residues received in the drying barter
    fugitive_baseline=0.025, fugitive_with_sensors=0.005,   # continuous laser/OGI methane-leak detection on digesters and upgraders
    sensor_sites=3, sensor_capex_gbp=40000.0, sensor_om_gbp=8000.0,
    asp_dmi_kg_day=dict(dairy=21.0, beef=12.0), asp_dose_dm=0.005, asp_bromoform_retention=0.70,
    asp_productivity_g_m2_day=12.0, asp_n_share_dw=0.03, asp_capex_gbp_m2=250.0, asp_om_frac=0.08,
    biogas_m3_ch4=dict(dairy=394.0, beef=150.0), food_waste_t=10000.0, food_waste_m3_ch4_t=60.0, ch4_mj_m3=35.8,
    ad_capex_gbp_per_gj_yr=40.0, ad_om_frac=0.05, biomethane_gbp_mwh=60.0,
    farm_diesel_l=dict(dairy=400.0, beef=100.0),
)
FARM_FUEL = dict(   # every farm in the eight communities' catchment (same 20% share of North East farmland as the cattle catchment)
    ne_farmed_ha=581_000,       # Defra June Survey 2024, North East total farmed area
    area_share=dict(cereals=0.19, general_cropping=0.14, horticulture=0.010, dairy=0.013, grazing_livestock=0.52, mixed=0.094, other=0.035),  # 2023
    red_l_per_ha=dict(cereals=100.0, general_cropping=130.0, horticulture=300.0, dairy=148.0, grazing_livestock=40.0, mixed=90.0, other=100.0),
    # red diesel incl. contractors (Defra FBS energy use: dairy 148 l/ha; 61% of LFA grazing farms <50 l/ha; others screening)
    red_diesel_gbp_l=0.78,      # pre-2026-crisis on-farm red diesel price (Farmers Weekly / BBC, Feb 2026)
    # subsidy closes the whole gap between bulk HVO (BACKUP['hvo_gbp_l']) and red diesel, so farmers pay the red-diesel price
)
AQUAFEED = dict(   # circular feed loop between finfish, prawns, greenhouse waste and local farms (screening)
    finfish_share=0.90, prawn_share=0.10, fcr_fish=1.2, fcr_prawn=1.5,
    fish_byproduct_share=0.45, prawn_byproduct_share=0.50, fish_meal_yield=0.22, prawn_meal_yield=0.25,
    feed_n_share=0.07, n_retained=0.30, n_dissolved_share=0.70,
    greenhouse_waste_share=0.20, bsf_yield_wet=0.15, bsf_meal_dm=0.30, tilapia_direct_greens_t_per_t=0.10,
    local_plant_share_fish=0.40, local_plant_share_prawn=0.30,     # wheat, barley, peas, faba beans, rapeseed meal from Tyne valley farms
    prawn_feed_marine_share=0.30,
    imported_feed_kg_co2e_kg=1.9, local_meal_kg_co2e_kg=0.4, bsf_kg_co2e_kg=0.6, local_plant_kg_co2e_kg=0.5,
)
UK_GHG = dict(territorial_mt_2024=373.0, population_m_2024=69.3)    # DESNZ final 2024 figures; ONS mid-2024 population
JOBS = dict(it_fte_per_mw=1.7, greenhouse_fte_per_ha=15, aquaculture_fte_per_t=0.09, renewable_fte_per_mw=0.12,
            processing_fte_per_t=0.04, vehicle_fte=35, logistics_fte=30, admin_fte=25, seaweed_pilot_fte=10,
            seaweed_fte_per_ha=5.0, feed_mill_fte=12, dh_households_per_fte=400, vehicles_per_fte=500, digester_fte=8,
            drying_fte_per_10gwh=1.0, block_fte=6, leak_detection_fte=2,
            wage_gbp=42000.0, oncost=0.20)

# ----------------------------------------------------------------------------------------------- GPU economics
COMPUTE = dict(
    products={
        "GB300 NVL72": dict(kw_per_gpu=135.0 / 72 * 1.10, capex_usd_per_gpu=6.0e6 / 72, price_factor=1.10),
        "Vera Rubin NVL72": dict(kw_per_gpu=220.0 / 72 * 1.10, capex_usd_per_gpu=8.45e6 / 72, price_factor=1.10),
    },
    price_start_usd={"reservation": 5.87, "on-demand": 8.98},
    price_step_usd_per_year=-1.0, cycle_years=4, residual=0.20, sold=0.85,
    generation_paths={"prices held each generation": 0.0, "prices compress 15% per generation": 0.15},
    facility_capex_usd_mw=10.0e6, maintenance_frac=0.025, insurance_frac=0.005, fte_per_mw=0.25, usd_per_fte=90000.0,
    tax=0.25, wacc=0.09, horizon=25,
)


# ----------------------------------------------------------------------------------------------- islanded 33 kV network
# Radial routes from the Hexham block along the valley roads (route km, screening); every route is a double circuit so that
# either circuit alone carries the full flow (N-1). 300 mm2 Al XLPE 33 kV cable: R 0.130, X 0.100 ohm/km, 450 A buried.
ISLAND = dict(
    routes=[("hexham", "corbridge", 6.0), ("hexham", "haydon_bridge", 10.0), ("hexham", "chollerford", 8.0),
            ("chollerford", "barrasford", 4.0), ("barrasford", "wark", 6.0), ("wark", "bellingham", 7.0), ("bellingham", "falstone", 14.0)],
    kv=33.0, r_ohm_km=0.130, x_ohm_km=0.100, ampacity_a=450.0, pf=0.95, circuits=2, v_limit=0.06,   # ESQCR +/-6% at HV
    gt_units=2, gt_unit_mw=55.0,            # two SGT-800-class units in combined cycle
)

# ----------------------------------------------------------------------------------------------- river rejection (local rule)
RIVER_RULE = dict(
    no_discharge_nodes=["falstone", "bellingham", "wark", "barrasford", "chollerford"],   # regulated North Tyne below Kielder: dry coolers only
    dT_limit_k=1.0, summer_months=[6, 7, 8, 9], summer_dT_limit_k=0.5,                   # precautionary summer limit for salmonid waters
)

# ----------------------------------------------------------------------------------------------- GB grid path scenarios
GRID_PATH_SCENARIOS = {"slower (100 g 2030, 50 g 2035, 25 g 2040)": {2030: 100.0, 2035: 50.0, 2040: 25.0},
                       "central (Clean Power 2030, CCC 2035)": {2030: 50.0, 2035: 10.0},
                       "faster (30 g 2030, 5 g 2035)": {2030: 30.0, 2035: 5.0}}

# ----------------------------------------------------------------------------------------------- surplus offtake scenarios
EXPORT_SCENARIOS = {"central: all surplus at hourly price": dict(cap_mw=None, price_share=1.0, constraint=0.0),
                    "merchant PPA: 90% of hourly price, 5% constraint curtailment": dict(cap_mw=None, price_share=0.90, constraint=0.05),
                    "export capped at 600 MW": dict(cap_mw=600.0, price_share=1.0, constraint=0.0),
                    "export capped at 400 MW, merchant PPA terms": dict(cap_mw=400.0, price_share=0.90, constraint=0.05),
                    "export capped at 200 MW, merchant PPA terms": dict(cap_mw=200.0, price_share=0.90, constraint=0.05)}

# ----------------------------------------------------------------------------------------------- community evidence tiers
COMMUNITY_TIER = {
    "Home heating and hot water through district loops and home heat pumps": "A", "Hot-fill washing and cleaning water": "A",
    "Household vehicles replaced by battery-electric and plug-in hybrid vehicles": "B", "Circular aquafeed replacing imported feed": "A",
    "Methane-leak detection on digesters and upgraders": "A", "Drying contracts (fossil-fired drying displaced)": "B",
    "Manure and crop residues to digesters (storage methane avoided)": "B", "Biomethane displacing natural gas": "B",
    "Farm red diesel replaced by subsidised HVO (all farms)": "B", "Renewable fuel for residents' remaining vehicles (HVO)": "B",
    "Free red seaweed (Asparagopsis) for dairy and beef cattle": "C"}
TIER_WEIGHT = {"A": 0.75, "B": 0.50, "C": 0.25}     # adoption x delivery likelihood used for the weighted central case (assumption)
