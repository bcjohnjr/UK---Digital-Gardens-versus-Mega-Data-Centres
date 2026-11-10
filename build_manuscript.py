#!/usr/bin/env python3
"""Build the manuscript, highlights and cover letter (DOCX) from the model outputs. Every number is read from OUTPUT/."""
import json
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import params as P

O = P.OUT; ROOT = P.HERE.parent; MS = ROOT / "MANUSCRIPT"; MS.mkdir(exist_ok=True); FIG = ROOT / "FIGURES"
d = json.load(open(O / "design.json")); dt = json.load(open(O / "design_trajectory.json")); hc = json.load(open(O / "heat_community.json"))
de = json.load(open(O / "design_econ.json")); ce = json.load(open(O / "compare_econ.json")); pw = json.load(open(O / "power_247.json"))
tr = json.load(open(O / "trajectory.json"))

S = d["selected"]; L = d["annual_load_gwh"]; MWH = L * 1e3
th = hc["heat"]["thermal"]; rv = hc["heat"]["rivers"]; fa = hc["heat"]["facts"]; pg = hc["programme"]; V = pg["vehicles"]; fd = hc["feed"]
CD = hc["sensitivities"]["continuous drying contracts at every node"]; HS = hc["sensitivities"]
LF, LN, LL, LNE = hc["ledger_full"], hc["ledger_no_asparagopsis"], hc["ledger_limited"], hc["ledger_north_east_seaweed"]
LED, LEDN, LEDL = LF["total_t"] / 1e3, LN["total_t"] / 1e3, LL["total_t"] / 1e3
EC = de["economics"]; PR = EC["premium"]; SENS = EC["sensitivity_musd"]; TAB = de["table"]; AB = de["absolute"]; CUM = dt["cum"]
OLD = ce["cumulative_25y"]; frp = {round(f["target"], 3): f for f in pw["frontier"]}
w0 = pw["website_portfolio"][0]
GB = dt["base_mean"]; G25 = dt["g2025"]
twin = AB["twin"]; cam = AB["cambois"]; sg = AB["stargate"]
six = d["sixteen_year"]; WT = d["wind_tests"]
trimix_max = max(o["trimix_hours"] for o in d["outage"]); trimix_years = sum(1 for o in d["outage"] if o["trimix_hours"] > 0)
min_out = min(o["hours"] for o in d["outage"])
DGLCA = TAB["2018-2025 observed"]["Digital Gardens"]; GRLCA = TAB["2018-2025 observed"]["Grid campus"]
g_on = PR["full|GB300 NVL72|on-demand"]; g_on_c = PR["capped|GB300 NVL72|on-demand"]; g_on_z = PR["zero|GB300 NVL72|on-demand"]
r_on = PR["full|Vera Rubin NVL72|on-demand"]
SOLAR_HA_PER_MWP = 1.4
RAW = d["raw_wind"]; RO = RAW["reoptimised"]; ISL_D = min(o["hours"] for o in d["outage"]) / 24
ISL = json.load(open(O / "island_network.json")); XS = EC_X = None
JB = de["jobs"]; AIGZ = EC["aigz"]; EXV = EC["export_value"]; ADV = EC["adverse_premium"]
CAPR = S["export_capture_gbp_mwh"] / S["mean_price_gbp_mwh"]
TIER = {  # evidence tier of each community measure
    "Home heating and hot water through district loops and home heat pumps": "A",
    "Hot-fill washing and cleaning water": "A",
    "Household vehicles replaced by battery-electric and plug-in hybrid vehicles": "B",
    "Circular aquafeed replacing imported feed": "A",
    "Methane-leak detection on digesters and upgraders": "A",
    "Drying contracts (fossil-fired drying displaced)": "B",
    "Manure and crop residues to digesters (storage methane avoided)": "B",
    "Biomethane displacing natural gas": "B",
    "Farm red diesel replaced by subsidised HVO (all farms)": "B",
    "Renewable fuel for residents' remaining vehicles (HVO)": "B",
    "Free red seaweed (Asparagopsis) for dairy and beef cattle": "C"}
XS = de["economics"]["export_scenarios"]; XR = json.load(open(O / "export_scenarios.json")); GPS = dt["scenarios"]
LW = hc["ledger_weighted"]; LEDW = LW["total_t"] / 1e3
TIER_SUM = {t: sum(v for k, v in LF["rows"].items() if TIER[k] == t) / 1e3 for t in "ABC"}


def f0(x): return f"{x:,.0f}"
def f1(x): return f"{(0.0 if abs(x) < 0.05 else x):,.1f}"
def f2(x): return f"{x:,.2f}"
def pc(x, dd=1): return f"{100 * x:.{dd}f}%"


# ---------------------------------------------------------------- 25-year cost account (2025 prices)
def pv(flows, r=P.COSTS["discount_rate"]):
    return sum(v / (1 + r) ** t for t, v in enumerate(flows, 1))


H = P.COSTS["horizon"]
supply_fixed = S["cost_full"] * MWH - (S["ppa"] - S["export_revenue"] + S["import_cost"])
noncomm = sum(P.COSTS["non_commodity_gbp_mwh"].values()) * MWH
veh_years = [y for y in range(1, H + 1) if ((y - 1) % V["life"]) < V["finance_years"]]
ACC = [  # (label, annual flow or list of 25 flows, capital at year 0)
    ("Contracted wind and solar output", S["ppa"], 0.0),
    ("Surplus sold to the grid", -S["export_revenue"], 0.0),
    ("Grid imports (energy)", S["import_cost"], 0.0),
    ("Battery and standby block (annualised capital, O&M, tank, test running)", supply_fixed, 0.0),
    ("Network and policy charges on consumption", noncomm, 0.0),
    ("Community programme: capital", 0.0, pg["capex_total"]),
    ("Community programme: operation and materials", pg["opex_total"], 0.0),
    ("Community programme: wages (excluding data-centre and energy staff)", EC["community_labour"], 0.0),
    ("Community programme: drying and biomethane income", -pg["revenue_total"], 0.0),
    ("Vehicle finance (84 months, renewed every 12 years)", [V["annual_finance_payment_gbp"] if y in veh_years else 0.0 for y in range(1, H + 1)], 0.0),
]
acc_rows = []
for lab, a, cap in ACC:
    flows = a if isinstance(a, list) else [a] * H
    acc_rows.append((lab, (flows[0] if not isinstance(a, list) else V["annual_finance_payment_gbp"]), cap + sum(flows), cap + pv(flows)))
TOT25 = sum(r[2] for r in acc_rows); TOTPV = sum(r[3] for r in acc_rows)
ENERGY25 = sum(r[2] for r in acc_rows[:5]); COMM25 = sum(r[2] for r in acc_rows[5:])
CAM25 = EC["cambois_delivered"] * MWH * H; CAMPV = pv([EC["cambois_delivered"] * MWH] * H)

# ---------------------------------------------------------------- references, numbered in order of first citation
REF = {  # RSC style
 "iea": "International Energy Agency, Energy and AI, IEA, Paris, 2025, https://www.iea.org/reports/energy-and-ai.",
 "dg": "Digital Gardens of the North Tyne Valley, project website (eight-community model and covenant design), https://digitalgardens.uk/, accessed 17 October 2026.",
 "qts": "QTS Data Centers, Cambois data centre campus, https://qtsdatacenters.com/data-centers/cambois, accessed 5 November 2026.",
 "corgan": "Corgan, QTS data center campus, Cambois, https://www.corgan.com/projects/qts-data-center-campus-cambois, accessed 5 November 2026.",
 "dcd": "DatacenterDynamics, Approval given to first phase of £10bn data center in Northumberland, England, 8 December 2025.",
 "sg": "OpenAI, Introducing Stargate UK, 16 September 2025, https://openai.com/index/introducing-stargate-uk/.",
 "sgpause": "Computer Weekly, OpenAI pauses Stargate UK: sudden setback or calculated move?, April 2026, https://www.computerweekly.com/news/366641483/.",
 "aigz": "Department for Science, Innovation and Technology, Delivering AI Growth Zones, policy paper, London, November 2025, https://www.gov.uk/government/publications/delivering-ai-growth-zones.",
 "era5": "H. Hersbach, B. Bell, P. Berrisford, S. Hirahara, A. Horányi, J. Muñoz-Sabater, J. Nicolas, C. Peubey, R. Radu, D. Schepers, A. Simmons, C. Soci, S. Abdalla, X. Abellan, G. Balsamo, P. Bechtold, G. Biavati, J. Bidlot, M. Bonavita, G. De Chiara, P. Dahlgren, D. Dee, M. Diamantakis, R. Dragani, J. Flemming, R. Forbes, M. Fuentes, A. Geer, L. Haimberger, S. Healy, R. J. Hogan, E. Hólm, M. Janisková, S. Keeley, P. Laloyaux, P. Lopez, C. Lupu, G. Radnoti, P. de Rosnay, I. Rozum, F. Vamborg, S. Villaume and J.-N. Thépaut, Q. J. R. Meteorol. Soc., 2020, 146, 1999–2049.",
 "om": "Open-Meteo, Historical Weather API: ECMWF ERA5 data access, https://open-meteo.com/en/docs/historical-weather-api, accessed 1 November 2026.",
 "staffell": "I. Staffell and S. Pfenninger, Energy, 2016, 114, 1224–1239.",
 "ruk": "RenewableUK, UK Wind Energy Database: statistics explained (DESNZ load factors 2020–2024 and CfD new-build load factors), https://www.renewableuk.com/page/UKWEDhome, accessed 1 November 2026.",
 "ar7": "Department for Energy Security and Net Zero, Contracts for Difference Allocation Round 7 results, London, 2026.",
 "neso": "National Energy System Operator, Carbon Intensity API (national and regional), 2018–2025, https://carbonintensity.org.uk.",
 "elexon": "Elexon, Insights Solution: Market Index Data, 2018–2025, https://data.elexon.co.uk.",
 "noncomm": "Energy Costs, Non-commodity charges explained, 2026, https://www.energycosts.co.uk/articles/non-commodity-charges/.",
 "riepin": "I. Riepin and T. Brown, Energy Strategy Rev., 2024, 54, 101488.",
 "riepin2": "I. Riepin, T. Brown and V. M. Zavala, Adv. Appl. Energy, 2025, 17, 100202.",
 "xu": "Q. Xu, W. Ricks, A. Manocha, N. Patankar and J. D. Jenkins, Joule, 2024, 8, 374–400.",
 "hvo_gt": "J. Runyon, S. James, B. Broughton, D. Graham, C. Goy, S. Duncan and J. Harman-Thomas, E3S Web Conf., 2025, 663, 01007.",
 "rtfo": "Department for Transport, Renewable Transport Fuel Obligation statistics 2024: final report, London, 2026.",
 "cp30": "National Energy System Operator, Clean Power 2030, NESO, Warwick, 2025.",
 "ccc": "Climate Change Committee, The Sixth Carbon Budget: electricity generation, CCC, London, 2020.",
 "ipcc_lca": "S. Schlömer, T. Bruckner, L. Fulton, E. Hertwich, A. McKinnon, D. Perczyk, J. Roy, R. Schaeffer, R. Sims, P. Smith and R. Wiser, in Climate Change 2014: Mitigation of Climate Change. Contribution of Working Group III to the Fifth Assessment Report of the Intergovernmental Panel on Climate Change, Cambridge University Press, Cambridge, 2014, Annex III.",
 "desnz_cf": "Department for Energy Security and Net Zero, Greenhouse gas reporting: conversion factors 2025, London, 2025.",
 "ofgem": "Ofgem, Typical domestic consumption values, https://www.ofgem.gov.uk, accessed 1 November 2026.",
 "census": "Office for National Statistics, Census 2021, table TS045: car or van availability, Northumberland, 2023.",
 "defra": "Department for Environment, Food and Rural Affairs, Agricultural facts: North East region, London, 2025.",
 "offgas": "North East Combined Authority, Mayor calls for urgent action to protect rural households from soaring heating oil prices, 13 March 2026.",
 "nrfa": "UK Centre for Ecology & Hydrology, National River Flow Archive, stations 23001 (Tyne at Bywell) and 23004 (South Tyne at Haydon Bridge), https://nrfa.ceh.ac.uk.",
 "egger": "Business Up North, Francis Brown delivers historic first for EGGER UK Ltd, 2023.",
 "hexdh": "Hexham Courant, Plans for district heating networks in Hexham and Prudhoe, 2023.",
 "roque": "B. M. Roque, M. Venegas, R. D. Kinley, R. de Nys, T. L. Duarte, X. Yang and E. Kebreab, PLoS One, 2021, 16, e0247820.",
 "gwp": "G. Myhre, D. Shindell, F.-M. Bréon, W. Collins, J. Fuglestvedt, J. Huang, D. Koch, J.-F. Lamarque, D. Lee, B. Mendoza, T. Nakajima, A. Robock, G. Stephens, T. Takemura and H. Zhang, in Climate Change 2013: The Physical Science Basis. Contribution of Working Group I to the Fifth Assessment Report of the Intergovernmental Panel on Climate Change, Cambridge University Press, Cambridge, 2013, ch. 8.",
 "amc": "American Compute, GPU cloud price comparison: GB200 and GB300, October 2026, https://www.amcompute.com/gpu-cloud-prices/gb200.",
 "vr": "Tom's Hardware, Price of Nvidia's Vera Rubin NVL72 racks, June 2026.",
 "secnewgate": "SEC Newgate, Public and councillor attitudes to data centres in the UK, 2026.",
 "yougov": "Cavendish Consulting and YouGov, Generational attitudes to local data centres, 2026.",
 "dpcia": "Dolphin Protection Consumer Information Act, 16 U.S.C. §1385, 1990.",
 "teisl": "M. F. Teisl, B. Roe and R. L. Hicks, J. Environ. Econ. Manage., 2002, 43, 339–359.",
 "gallup": "Gallup, Americans oppose AI data centers in their area, 13 May 2026.",
 "huang": "P. Huang, B. Copertaro, X. Zhang, J. Shen, I. Löfgren, M. Rönnelid, J. Fahlen, D. Andersson and M. Svanfeldt, Appl. Energy, 2020, 258, 114109.",
 "wahlroos": "M. Wahlroos, M. Pärssinen, S. Rinne, S. Syri and J. Manner, Renewable Sustainable Energy Rev., 2018, 82, 1749–1764.",
 "ebrahimi": "K. Ebrahimi, G. F. Jones and A. S. Fleischer, Renewable Sustainable Energy Rev., 2014, 31, 622–638.",
 "chen": "X. Chen, J. Bai, L. Fu, Y. Lei, D. Zhang, Z. Zhang, Q. Luo, S. Gong and B. Shen, J. Cleaner Prod., 2024, 435, 140495.",
 "ljungqvist": "H. Markeby Ljungqvist, L. Mattsson, M. Risberg and M. Vesterlund, Energy, 2021, 215, 119169.",
 "llama": "Llama Team, AI @ Meta, The Llama 3 herd of models, arXiv, 2024, preprint, arXiv:2407.21783.",
 "epoch": "Epoch AI, AI training cluster sizes increased by more than 20x since 2016, https://epoch.ai, accessed 1 November 2026.",
 "spectrum": "NVIDIA, NVIDIA introduces Spectrum-XGS Ethernet to connect distributed data centers, 25 August 2025.",
 "hvo_price": "123oil, How much is HVO fuel per litre?, 2026, https://www.123oil.co.uk.",
 "chopin": "T. Chopin, A. H. Buschmann, C. Halling, M. Troell, N. Kautsky, A. Neori, G. P. Kraemer, J. A. Zertuche-González, C. Yarish and C. Neefus, J. Phycol., 2001, 37, 975–986.",
 "scheutz": "C. Scheutz and A. M. Fredenslund, Waste Manage., 2019, 97, 38–46.",
 "fbs": "Department for Environment, Food and Rural Affairs, Energy use on farms in England 2023/24, London, 2025.",
 "reddiesel": "Farmers Weekly, Red diesel prices spike by 60% as supplies remain tight, March 2026.",
 "ukghg": "Department for Energy Security and Net Zero, Final UK greenhouse gas emissions national statistics: 1990 to 2024, London, 2026.",
}
ORDER = []


def C(*keys):
    for k in keys:
        assert k in REF, k
        if k not in ORDER:
            ORDER.append(k)
    nums = sorted(ORDER.index(k) + 1 for k in keys)
    parts, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        parts.append(f"{nums[i]}–{nums[j]}" if j - i >= 2 else ",".join(str(n) for n in nums[i:j + 1]))
        i = j + 1
    return "[" + ",".join(parts) + "]"


TITLE = ("Digital Gardens versus QTS Cambois and Stargate UK: carbon, water, energy and economics of a renewable, heat-sharing "
         "distributed AI network in the North Tyne valley and grid-supplied AI campuses in Northumberland")

doc = Document()
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
for s_ in doc.sections:
    s_.left_margin = s_.right_margin = Cm(2.2); s_.top_margin = s_.bottom_margin = Cm(2.0)


def para(text, bold=False, italic=False, size=None, align=None, space=6):
    p = doc.add_paragraph(); r = p.add_run(text); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if align is not None: p.alignment = align
    p.paragraph_format.space_after = Pt(space)
    return p


def head(text, level=1):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.color.rgb = RGBColor(0x0b, 0x0b, 0x0b); r.font.name = "Calibri"
    return h


def table(rows, caption, size=8.5):
    para(caption, bold=True, size=9, space=3)
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Light Grid Accent 1"
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.text = ""; r = c.paragraphs[0].add_run(str(v)); r.font.size = Pt(size); r.bold = i == 0
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def landscape(on):
    return
    from docx.enum.section import WD_ORIENT, WD_SECTION
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    w, h = sec.page_width, sec.page_height
    if (on and w < h) or (not on and w > h):
        sec.orientation = WD_ORIENT.LANDSCAPE if on else WD_ORIENT.PORTRAIT
        sec.page_width, sec.page_height = h, w
    sec.left_margin = sec.right_margin = Cm(2.2); sec.top_margin = sec.bottom_margin = Cm(2.0)


def figure(name, caption, width=16):
    doc.add_picture(str(FIG / f"{name}.png"), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(caption, italic=True, size=8.5)


# ================================================================ front matter
para(TITLE, bold=True, size=15, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Jonathan Karl Bily", align=WD_ALIGN_PARAGRAPH.CENTER, space=2)
para("Independent Researcher, Zaragoza, Spain · jonathan@cloudwashlaundry.com", italic=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, space=12)

head("Abstract", 1)
para(f"QTS is building a 720 MW grid-supplied AI campus at Cambois, Northumberland, and Stargate UK proposed up to 31,000 GPUs at nearby "
     f"Cobalt Park before it was paused in April 2026. Digital Gardens proposes eight riverside nodes with {f1(P.NETWORK['it_mw'])} MW of IT "
     f"in the North Tyne and Tyne valleys that share their heat, food and vehicles with {f0(fa['population'])} residents. Supply is "
     f"dispatched in a fixed order — contracted wind and solar, a battery, the grid, and a 110 MW combined-cycle block on renewable fuel only "
     f"when the grid has failed. Cambois and Stargate UK are represented by modelled grid-supplied twins built from their announced "
     f"characteristics, not by operating records. With ERA5 weather for 2010–2025 and GB grid data for 2018–2025, the least-cost portfolio with a battery of "
     f"at most 400 MWh that supplies 80% of consumption from its own wind and solar hour by hour has {f0(S['wind_mw'])} MW of wind and "
     f"{f0(S['solar_mwp'])} MWp of solar when wind speeds are scaled to a 30% fleet capacity factor, and {f0(RO['wind_mw'])} MW and "
     f"{f0(RO['solar_mwp'])} MWp with unscaled ERA5 winds; it costs £{f1(S['cost_full'])}–{f1(RO['cost_full'])}/MWh against "
     f"£{f1(d['comparator']['energy_gbp_mwh'])}/MWh for grid power with annual certificates, provided that about "
     f"{f0(S['export_gwh'])} GWh a year of surplus is sold at hourly market prices (£{f1(XS['merchant PPA: 90% of hourly price, 5% constraint curtailment']['energy_gbp_mwh'])}–"
     f"{f1(XS['export capped at 200 MW, merchant PPA terms']['energy_gbp_mwh'])}/MWh under merchant offtake terms and export caps). A screening "
     f"load-flow and N-1 study of a double-circuit 33 kV island network shows that, if the grid fails, the nodes could run for "
     f"{f1(ISL_D)} days on the battery and the block's stored fuel, conditional on protection and stability studies. Over 2027–2051 the network emits {f0(CUM['dg_lca_kt'])} kt CO₂e on a "
     f"life-cycle basis against {f0(CUM['twin_lca_kt'])} kt for the modelled grid twin of the same IT ({pc(1 - CUM['dg_lca_kt'] / CUM['twin_lca_kt'], 0)} "
     f"less; {pc(1 - GPS['faster (30 g 2030, 5 g 2035)']['dg_lca_kt'] / GPS['faster (30 g 2030, 5 g 2035)']['twin_lca_kt'], 0)}–"
     f"{pc(1 - GPS['slower (100 g 2030, 50 g 2035, 25 g 2040)']['dg_lca_kt'] / GPS['slower (100 g 2030, 50 g 2035, 25 g 2040)']['twin_lca_kt'], 0)} "
     f"under faster and slower grid decarbonisation). Host-community measures — hot water to every household, bartered farm drying, digesters with methane-leak detection, circular "
     f"aquafeed, subsidised farm HVO, vehicle replacement and, if approved, free red-seaweed feed for cattle — could avoid "
     f"{f0(LEDW)} kt CO₂e a year relative to current practice in an adoption-weighted central case, close to the {f0(LEDL)} kt of limited "
     f"adoption; full deployment would avoid {f0(LED)} kt. The towns use {pc(th['used_share_of_recoverable'], 0)} of recoverable server heat. A break-even "
     f"clean-compute premium of US${f2(g_on['premium'])} per GB300 GPU-hour ({pc(g_on['share_of_price'])} of the on-demand price) recovers "
     f"the full 25-year cost; customer willingness to pay it is untested. All results are conditional scenarios, not demonstrated site "
     f"feasibility.")
para("Keywords: AI data centres; hourly renewable matching; waste-heat reuse; integrated multi-trophic aquaculture; Asparagopsis; AI Growth Zone; Northumberland",
     italic=True, size=9.5)
BROADER = (f"AI data centres are becoming some of the largest single electricity loads in Britain, and where they are built and how they are "
           f"supplied will shape both the national grid and the communities around them. Most new campuses buy grid power matched annually "
           f"with certificates and return little to their neighbours. This analysis tests an alternative for a rural English valley: small "
           f"computing nodes that buy roughly twice their consumption in wind and solar, sell the surplus, keep a renewable-fuel reserve for "
           f"grid failure, and give their heat, food and vehicle services to the towns that host them. Using sixteen years of hourly weather "
           f"and eight years of grid data, it shows what such a network would cost, how much of its electricity it could supply itself, how "
           f"long it could run without the grid, how much of its waste heat small towns can actually use, and how large the host-community "
           f"emission reductions could be against those of a conventional campus. The result is a quantified, reproducible template that "
           f"planners, communities and AI operators can test against measured wind, contracted fuel and real customers before any site is "
           f"chosen.")
assert len(BROADER.split()) <= 200, len(BROADER.split())
head("Broader context", 1)
para(BROADER)

# ================================================================ 1 introduction
head("1. Introduction", 1)
para(f"AI computing is adding large, continuous loads to electricity systems {C('iea')}. In north-east England two contrasting models are in play, "
     f"and this paper compares them on carbon, water, energy and economics. The North East AI Growth Zone spans Blyth/Cambois and Cobalt Park "
     f"{C('aigz')}. At Cambois, QTS, owned by Blackstone, holds permission for up to ten data-centre buildings of 72 MW of IT each, 720 MW in "
     f"total, on the site of the former Blyth Power Station, supplied from an on-site substation and cooled by waterless closed-loop "
     f"free-cooling chillers {C('qts', 'corgan')}; the first two buildings were approved in December 2025 {C('dcd')}. QTS states that it will "
     f"explore the viability of supplying a district heating network with Northumberland County Council, with no heat-reuse commitment made "
     f"{C('qts')}. Stargate UK, announced by OpenAI, NVIDIA and Nscale in September 2025, planned an offtake of up to 8,000 GPUs in early 2026 "
     f"with potential to reach 31,000, at sites including Cobalt Park {C('sg')}; OpenAI paused the project in April 2026, citing energy costs "
     f"and regulation, and Cobalt Park currently hosts about 35 MW with no planning application lodged for expansion {C('sgpause')}. Data "
     f"centres in the zone may receive an electricity discount of up to £14/MWh from April 2027 {C('aigz')}.")
para(f"Digital Gardens is a proposal for eight nodes on the North Tyne, South Tyne and Tyne — Falstone, Bellingham, Wark, Barrasford, Chollerford, "
     f"Haydon Bridge, Hexham and Corbridge — sized at 4.46 kW of IT per resident, {f1(P.NETWORK['it_mw'])} MW in total, whose heat, food and "
     f"vehicles are offered to the {f0(fa['population'])} residents of communities that adopt a fossil-free covenant {C('dg')}. It is a UK "
     f"counterpart of a proposed British Columbia network. Earlier work has examined hourly "
     f"('24/7') carbon-free procurement {C('riepin', 'riepin2', 'xu')}, spatial and temporal load shifting {C('riepin2')} and data-centre heat "
     f"for district heating, greenhouses and farms {C('huang', 'wahlroos', 'ebrahimi', 'chen', 'ljungqvist')}. Less is known about how a "
     f"grid-connected AI load should size its own renewables and storage when surplus can be sold, what firm backup it needs if the grid "
     f"fails, how much server heat small rural towns can use hour by hour, and what a host-community programme built around that heat — "
     f"food, feed, seaweed, digesters and vehicles — can do to the carbon budgets of the people who live next to it.")
para(f"Public acceptance is a constraint in Britain too. In a 2026 survey of more than 1,500 adults, 60% said they would accept more data "
     f"centres locally while 40% would not even when national benefits were explained; 67% thought data centres use too much power and 55% "
     f"were worried about water {C('secnewgate')}. In YouGov polling for Cavendish, 44% of Gen Z respondents would support a new data centre "
     f"in their area and 31% would oppose one, citing the local environment, energy supply and water {C('yougov')}. In the United States, 71% "
     f"of adults opposed an AI data centre in their area in 2026 {C('gallup')}. A network that communities accept has to show where its "
     f"electricity comes from in every hour, consume no cooling water, keep running when the grid does not, and return benefits that "
     f"residents can see.")
para("This paper addresses six questions. (i) At the same IT load, how do Digital Gardens and a Cambois- or Stargate-type grid campus compare "
     "in carbon on operational and life-cycle bases, in water and in jobs, once host-community reductions are counted? (ii) What mix of wind, "
     "solar and a reasonably sized battery supplies most of the network's consumption hour by hour at least cost when surplus is sold, and "
     "how long can it run if the grid fails? (iii) How robust is that design to wind yield and weather? (iv) How do its emissions evolve as "
     "Great Britain moves to Clean Power 2030? (v) How much server heat can the eight towns use — for homes, greenhouses, aquaculture, "
     "seaweed, digesters and drying — and how efficient is the network if drying is contracted continuously? (vi) What can the host-community "
     "programme deliver in emissions, food and jobs, what does it all cost over the 25-year life of the renewables, and what clean-compute "
     "premium recovers that cost in a GPU rental business?")

# ================================================================ 2 methods
head("2. Methods", 1)
head("2.1 Load, weather and grid data", 2)
ci = d["community_info"]
para(f"Average IT draw is 90% of installed IT ({f1(pw['it_mw_avg'])} MW) at a power usage effectiveness (PUE) of {P.NETWORK['pue']:.2f}. The "
     f"community programme adds {f1(d['community_mw'])} MW for greenhouses, aquaculture, seaweed circulation, processing, home heat pumps and "
     f"the charging of {f0(V['total'])} vehicles ({f1(ci['vehicles']['charging_gwh'])} GWh a year), so the network load is "
     f"{f1(d['load_mw'])} MW, {f0(L)} GWh a year. Hourly 100 m wind, global and direct irradiance and temperature come from ERA5 {C('era5')} "
     f"via Open-Meteo {C('om')} for 2010–2025 at the eight nodes, four Northumberland wind proxies (Kielder uplands, Wark Forest, Ridsdale and "
     f"the coast) and the two comparator sites. A generic 4–5 MW turbine curve gives an unscaled fleet capacity factor of "
     f"{pc(WT['raw']['fleet_cf'])}; speeds are scaled by {f2(WT['0.3']['scale'])} to a central 30%, between the GB onshore fleet's 25.3% for "
     f"2020–2024 and the 36% that DESNZ uses for new projects {C('ruk')}, with bias-corrected reanalysis as the usual approach "
     f"{C('staffell')}. Solar output is computed on a south-facing plane at 35° from global and direct irradiance with a performance ratio of "
     f"0.82 and a temperature correction, giving a capacity factor of {pc(pw['pv_cf'])}. Half-hourly GB national carbon intensity and North "
     f"East England regional intensity come from the NESO Carbon Intensity API and half-hourly wholesale prices from Elexon market index data, "
     f"2018–2025 {C('neso', 'elexon')}. The regional series reflects generation in the region (mean about 38 g/kWh) rather than the "
     f"electricity consumed there; the GB national series (mean {f0(GB)} g/kWh, {f0(G25)} g/kWh in 2025) is the location basis, as Great "
     f"Britain is a single grid.")

head("2.2 Supply design and dispatch order", 2)
B = P.BACKUP
para(f"Digital Gardens buys the output of contracted onshore wind and solar at the CfD Allocation Round 7 strike prices, £72.24/MWh and "
     f"£65.23/MWh (2024 prices) {C('ar7')}. In every hour load is served in a fixed order: from wind and solar; then from a four-hour battery "
     f"(94% each way, £250/kWh); then from the grid; and only if the grid is unavailable from the backup block. Surplus wind and solar charge "
     f"the battery and the remainder is sold to the grid at the hourly wholesale price, or curtailed when prices are negative. The design "
     f"case is the least-cost portfolio that (a) supplies at least {pc(P.COSTS['self_supply_target'], 0)} of consumption from its own wind, "
     f"solar and battery hour by hour, averaged over the 2018–2025 weather years; (b) keeps the battery to a reasonable size, at most "
     f"{f0(P.COSTS['battery_max_mwh'])} MWh, about four hours of network load; and (c) contracts no more than "
     f"{P.COSTS['sellback_limit']:.0f} times annual consumption, so that about half its output is sold back. A grid of {f0(d['search']['n'])} "
     f"portfolios spans wind 0–1,200 MW, solar 0–1,200 MWp and battery 0–400 MWh. Every year's hourly prices are rescaled to the 2025 mean; "
     f"observed prices, surplus valued only up to the contract price, surplus sold at 80% and 60% of the hourly price (capture-price "
     f"erosion as more solar is built), and surplus given no value are sensitivities. Realistic offtake is tested by re-dispatching the "
     f"design with the surplus sold through a merchant PPA at 90% of the hourly price with 5% constraint curtailment, and with exports capped "
     f"at 600, 400 and 200 MW to represent grid constraints on the contracted plants (surplus above the cap is curtailed). The contracted plants hold their own grid "
     f"connections and sell their output through a sleeved power purchase agreement; Digital Gardens does not export through its own "
     f"connections, so the export risk it carries is a price risk on the share of contracted output it does not consume, not a "
     f"network-access risk. Battery capital is annualised at 6% over 15 years with a mid-life replacement. Because unscaled ERA5 winds give "
     f"a fleet capacity factor of only {pc(WT['raw']['fleet_cf'])}, the search is repeated with unscaled winds and both designs are "
     f"reported.")
para(f"The backup block is a {f0(B['mw'])} MW combined cycle of two SGT-800-class gas turbines, a class already in HVO service {C('hvo_gt')}, "
     f"at {pc(B['efficiency'], 0)} efficiency with an air-cooled condenser, £1,300/kW, £20/kW-yr fixed and £5/MWh variable costs. It burns "
     f"hydrotreated vegetable oil (HVO, 34.4 MJ/L, £{f2(B['hvo_gbp_l'])}/L bulk {C('hvo_price')}) from a tank holding 14 days at full output "
     f"({f1(d['tank_ml'])} ML); when the tank falls below one third it switches to a tri-mix of HVO, biodiesel (B100, 30% of the liquid) and "
     f"biogas from the local digesters (up to half of fuel energy, from a three-day gas buffer). In normal operation it runs only for monthly "
     f"one-hour tests ({f0(d['test_mwh'])} MWh a year). The block stands at the Hexham node, which carries more than half of the IT, and reaches "
     f"the other seven nodes over a private radial 33 kV network along the valley roads ({f0(ISL['route_km'])} route-km: Hexham to Corbridge, "
     f"to Haydon Bridge, and up the North Tyne through Chollerford, Barrasford, Wark and Bellingham to Falstone). Every route is a double "
     f"circuit of 300 mm² aluminium XLPE cable (0.130 + j0.100 Ω/km, 450 A), so that either circuit alone carries the full flow; with "
     f"islanding switchgear it costs £{f0(ISL['capex_gbp'] / 1e6)} million (£{f1(B['island_network_gbp_km'] / 1e6)} million per circuit-km plus "
     f"£{f0(B['island_switchgear_gbp'] / 1e6)} million). A steady-state load flow at full load (power factor 0.95, approximate AC voltage "
     f"drop on each radial segment) checks thermal loading and voltage against the ±6% statutory limit at 33 kV, with both circuits and "
     f"with each single circuit out (N-1), and the loss of one of the two turbine units is assessed against the battery. Protection "
     f"coordination and dynamic stability are not modelled; the batteries' inverters are assumed to be grid-forming and the block to have "
     f"black-start capability. The battery is divided among the nodes. The contracted wind and solar plants are remote and sleeved through the public grid, so they are not available to "
     f"the nodes when the grid fails. The block's capital, fixed costs, tank, fuel inventory, test running and the private network, "
     f"£{f1(d['standby_gbp'] / 1e6)} million a year, are charged to the design. Resilience is tested by a complete grid outage starting at "
     f"the worst fortnight of each weather year (the largest 14-day renewable deficit), counting the hours the islanded nodes can carry full "
     f"load from the battery and the block without fuel deliveries; a second case, conditional on the contracted plants also being "
     f"connected to the private network, is reported for comparison. The selected portfolio is also replayed over all sixteen weather years and at wind fleet "
     f"capacity factors of 25.3%, 30% and 36% and with unscaled ERA5 winds.")

head("2.3 Comparators, accounting bases and the GB decarbonisation path", 2)
rows = [["Item", "Announced (source)", "Modelled assumption"],
        ["QTS Cambois IT capacity", "Up to 10 × 72 MW = 720 MW; first two buildings approved Dec 2025 (refs. 3–5)", "720 MW IT; same-IT twin at 93.5 MW"],
        ["QTS Cambois cooling", "Waterless closed-loop free-cooling chillers (ref. 3)", "No cooling water"],
        ["QTS Cambois heat reuse", "District heating to be explored; no commitment (ref. 3)", "None"],
        ["QTS Cambois jobs", "About 400 operational (ref. 3)", "400"],
        ["Stargate UK", "Up to 8,000 GPUs, potential 31,000; paused April 2026 (refs. 6,7)", "8,000 and 31,000 GB300 GPUs, 2.06 kW each"],
        ["Electricity supply and sourcing", "Grid connection; no published PPA or hourly-matching commitment", "GB grid at hourly price + annual certificates at £5/MWh"],
        ["PUE and utilisation", "Not published", "PUE 1.20, 90% utilisation"],
        ["Growth Zone discount", "Up to £14/MWh for eligible projects from April 2027, review 2030 (ref. 2)", "Full £14/MWh for 25 years (central)"]]
table(rows, "Table 1. Announced characteristics of the comparators and the assumptions used to model them.", size=7.5)
para(f"The comparators are modelled grid-supplied campuses at a PUE of 1.20 and 90% utilisation: QTS Cambois at 720 MW of IT and Stargate UK at 8,000 "
     f"and 31,000 GB300 GPUs (2.06 kW per GPU, 16.5 and 63.9 MW). A twin of each at Digital Gardens' {f1(P.NETWORK['it_mw'])} MW of IT buys grid "
     f"power at the hourly price plus annual certificates at £5/MWh. Non-commodity charges of "
     f"£{f1(sum(P.COSTS['non_commodity_gbp_mwh'].values()))}/MWh (transmission and balancing {C('noncomm')}, renewables and capacity levies "
     f"and the climate change levy) apply to all consumption of both designs. The comparators also receive the Growth Zone discount of up "
     f"to £14/MWh {C('aigz')}; it is an upper bound for eligible projects, subject to implementation and a review in 2030. The central case "
     f"applies the full £14/MWh for all 25 years, which favours the comparators, and the discount ending after 2030 or never being granted "
     f"are sensitivities. "
     f"Emissions are counted on two bases. The operational basis is location-based grid imports at hourly GB intensity plus combustion. The "
     f"life-cycle basis adds 11 g/kWh for wind, 35 g/kWh for solar and 70 kg CO₂e/kWh of battery over 15 years {C('ipcc_lca')}, attributed "
     f"to the share of output consumed rather than sold; 21.6 g CO₂e/MJ for HVO and B100, the 77% saving against fossil fuel reported under "
     f"the Renewable Transport Fuel Obligation for 2024 including indirect land-use change {C('rtfo')}; and 10 g/MJ for biogas. Grid "
     f"electricity on the life-cycle basis carries a 20% upstream share and 12 g/kWh embodied in low-carbon generation. Electricity sold to "
     f"the grid carries its life-cycle emissions away with it and earns no avoided-emission credit. For 2027–2051 the hourly GB intensity "
     f"shapes are rescaled to a path from the observed 2025 mean to the Clean Power 2030 level of 50 g/kWh {C('cp30')} and 10 g/kWh in 2035 "
     f"{C('ccc')}, a policy-aligned path; a slower path (100 g/kWh in 2030, 50 in 2035, 25 in 2040) and a faster one (30 g/kWh in 2030, "
     f"5 in 2035) are sensitivities. For comparison, a fossil-free-first rule is also run, in which the block runs before any grid import.")

head("2.4 Heat: hot-water lines, home heat pumps, seaweed and drying", 2)
HT = P.HEAT
para(f"85% of IT heat is captured at 45–55 °C and 15% is lost in distribution. Hot-water lines are run to every household in the covenant "
     f"communities ({f0(pg['connected_households'])}). Each home has a small water-to-water heat pump (seasonal COP {HT['hp_cop']:.0f}) that lifts "
     f"the {HT['loop_c']:.0f} °C loop to {HT['dhw_c']:.0f} °C for hot water and to radiator temperature on the coldest days; it supplies "
     f"{pc(fa['hw_lift_share'], 0)} of hot-water heat and {pc(HT['space_hp_lift_share'], 0)} of space heat, and its electricity "
     f"({f1(th['home_hp_el_gwh'])} GWh a year) is part of the network load. Space heat comes from a degree-hour model on each node's own ERA5 "
     f"temperature (base 15.5 °C), with heat loss calibrated so that a Hexham household uses the Ofgem typical 11,500 kWh of gas a year at 85% "
     f"boiler efficiency {C('ofgem')}; hot water is 50 L per person per day; and hot-fill washing machines, dishwashers and cleaning water add "
     f"{f1(HT['washing_mwh_hh'])} MWh per household a year. For each node and hour, heat goes first to homes, then to greenhouses "
     f"({f1(fa['greenhouse_ha'])} ha), fish and prawn tanks, red-seaweed tanks ({f1(fa['asparagopsis_ha'])} ha at "
     f"{f0(HT['seaweed_mwh_per_ha'])} MWh/ha a year) and digesters at that node, then to drying contracts at that node, seasonal first. Heat "
     f"cannot move between nodes. Heat no customer takes is rejected without evaporation, by a local rule: the five North Tyne nodes, on a "
     f"regulated river below Kielder, use dry coolers only; Haydon Bridge may discharge to the South Tyne up to a fully mixed rise of 1 °C "
     f"at its Q95 flow (2.16 m³/s); and Hexham and Corbridge share the rest of a 1 °C budget at the Q95 flow of the Tyne at Bywell "
     f"(6.12 m³/s) {C('nrfa')}, reduced to 0.5 °C in June–September as a precaution for salmonid waters. Anything else goes to dry coolers.")
para(f"The drying contracts are screening estimates. The largest is low-temperature pre-drying of wet wood chips ahead of the drum "
     f"dryers of the Hexham panel-board plant, whose energy plant supplies 35 MW of hot gas to its dryers from its own wood residue "
     f"{C('egger')}, and which has considered a district heating scheme of its own {C('hexdh')}; no fossil credit is taken for it. Two "
     f"contracts serve local farmers — grain drying in August–October and barn drying of hay, haylage, straw and farm woodchip in May–September "
     f"— and are paid not in cash but in manure and crop residues for the digesters. Other customers pay 25% less than their present cost of "
     f"the same useful heat. Thermal efficiency is reported four ways: the share of recoverable heat used; the share of all IT heat used; the "
     f"energy reuse factor (ERF, heat used divided by facility electricity); and a useful-energy efficiency, (IT electricity + heat used) "
     f"divided by facility electricity. A continuous-drying case adds year-round drying contracts at every node, sized to take all heat "
     f"that would otherwise be rejected.")

head("2.5 Host-community programme", 2)
LV = P.LIVESTOCK; AQ = P.AQUAFEED
para(f"Food. Greenhouses supply 146 kg of fresh produce and fish and prawn farms 46 kg of live-weight seafood per resident a year "
     f"({f0(fa['veg_t'])} t and {f0(fa['seafood_t'])} t). The aquaculture is {pc(AQ['finfish_share'], 0)} finfish and {pc(AQ['prawn_share'], 0)} "
     f"prawns by weight, with feed conversion ratios of {AQ['fcr_fish']} and {AQ['fcr_prawn']}. Feed is made in a circular loop: processing "
     f"by-products of the prawns are dried (with server heat) into prawn meal for the fish, and those of the fish into fish meal for the prawns; "
     f"{pc(AQ['greenhouse_waste_share'], 0)} of greenhouse output that is not sold becomes either direct green feed for herbivorous fish or "
     f"substrate for black soldier fly larvae, dried to insect meal; and wheat, barley, peas, faba beans and rapeseed meal from Tyne valley "
     f"farms supply {pc(AQ['local_plant_share_fish'], 0)} of fish feed and {pc(AQ['local_plant_share_prawn'], 0)} of prawn feed. Imported "
     f"feed (1.9 kg CO₂e/kg) is credited against local meal (0.4), insect meal (0.6) and local plant protein (0.5).")
para(f"Seaweed and cattle. The dissolved nitrogen in fish and prawn effluent ({f1(fd['n_dissolved_t'])} t a year) feeds land-based tanks of "
     f"the red seaweed Asparagopsis, an integrated multi-trophic arrangement {C('chopin')}; at {LV['asp_productivity_g_m2_day']:.0f} g dry "
     f"weight per m² a day and {pc(LV['asp_n_share_dw'], 0)} nitrogen the effluent could support {f0(fd['seaweed_capacity_t_dw'])} t of dry "
     f"seaweed a year. The seaweed is given free to dairy and beef farmers in a catchment of 20% of the North East's herds {C('defra')} "
     f"({f0(fa['dairy'])} dairy and {f0(fa['beef'])} beef cattle), fed at {pc(LV['asp_dose_dm'], 1)} of dry-matter intake with "
     f"{pc(LV['asp_bromoform_retention'], 0)} of its bromoform retained after drying, giving enteric methane cuts of 30% (dairy, 90% of the "
     f"year) and 68% (beef, 150 days of finishing) {C('roque')}; this needs {f0(fa['asparagopsis_t_dw'])} t of dry seaweed from "
     f"{f1(fa['asparagopsis_ha'])} ha of tanks. Asparagopsis is not authorised as a feed additive in Great Britain, so results are reported "
     f"with and without it, and for the whole North East herd as a sensitivity.")
para(f"Digesters and methane. Manure from the catchment herds, 10 kt of food waste and {f0(LV['crop_residue_t'])} t of crop residues received "
     f"in the drying barter go to digesters; avoided manure-storage methane is counted at {pc(LV['ad_storage_reduction'], 0)} of the storage "
     f"emission. Biogas not needed by the block is upgraded to biomethane and displaces natural gas. Digesters and upgraders lose "
     f"{pc(LV['fugitive_baseline'], 1)} of methane production without monitoring, within the range measured at European plants "
     f"{C('scheutz')}; continuous laser and optical gas-imaging leak detection at {LV['sensor_sites']} sites, with repair, is assumed to cut "
     f"this to {pc(LV['fugitive_with_sensors'], 1)}. Methane uses GWP100 = 28 {C('gwp')}.")
FF = P.FARM_FUEL; ffl = sum(FF['area_share'][k] * FF['red_l_per_ha'][k] for k in FF['area_share'])
para(f"Farm fuel. Every farm in the catchment — the same 20% of the North East's {f0(FF['ne_farmed_ha'] / 1e3)} thousand ha of farmland "
     f"{C('defra')}, {f0(FF['ne_farmed_ha'] * LV['catchment_share'] / 1e3)} thousand ha — switches its red diesel to HVO, including fuel "
     f"used by contractors. Fuel use is weighted by the region's farmed area by type (grazing livestock 52%, cereals 19%, general cropping "
     f"14%, mixed 9.4%, dairy 1.3%) at 40–148 L/ha, the dairy figure and the low use of upland grazing farms following the Farm Business "
     f"Survey {C('fbs')}, an average of {f0(ffl)} L/ha and {f1(LF['farm_hvo_ml'])} ML a year. The programme pays the whole difference "
     f"between bulk HVO (£{f2(P.BACKUP['hvo_gbp_l'])}/L) and red diesel (£{f2(FF['red_diesel_gbp_l'])}/L before the 2026 price spike "
     f"{C('reddiesel')}), £{f2(P.BACKUP['hvo_gbp_l'] - FF['red_diesel_gbp_l'])}/L, so farmers pay no more than they do now: "
     f"£{f1(pg['opex']['farm_hvo_subsidy'] / 1e6)} million a year.")
MB = P.MOBILITY
para(f"Homes and vehicles. Displaced home heating follows each node's share of homes off the gas grid (10–15% in Hexham and Corbridge, "
     f"70–90% in the North Tyne villages {C('offgas')}), with oil, LPG and electric heating in the proportions 60:15:25 and DESNZ combustion "
     f"factors {C('desnz_cf')}. Every car or van in a covenant household is replaced one for one by a battery-electric "
     f"({pc(1 - MB['phev_share'], 0)}) or plug-in hybrid vehicle ({pc(MB['phev_share'], 0)}, half its distance electric), and every household "
     f"without one receives one: with the Census 2021 distribution of 19.7% of households with no car, 43.1% with one, 28.1% with two and 9.1% "
     f"with three or more {C('census')}, the {f0(V['households'])} households receive {f0(V['total'])} vehicles ({f0(V['bev'])} "
     f"battery-electric, {f0(V['phev'])} hybrid; {f0(V['new_for_zero_car'])} to households that had none). Vehicles cost £30,000 and £32,000, "
     f"are financed over 84 months at 6.5% — the longest standard UK car-finance term, which spreads any taxable benefit to residents over as "
     f"many years as possible — and are replaced every 12 years. Each is driven 11,000 km a year at 17 kWh/100 km. Residents' remaining "
     f"diesel use receives 200 L of HVO per person a year.")
para(f"Percentages. Reductions are expressed against three baselines: the emissions of the activities the measures address (home heating "
     f"and washing, household vehicles, catchment cattle, manure storage, farm diesel, fossil-fired drying and imported feed, "
     f"{f0(LF['baselines']['addressed_sectors_t'] / 1e3)} kt a year); residents' share of UK territorial emissions, "
     f"{f2(LF['baselines']['uk_per_capita_t'])} t per person ({f0(LF['baselines']['residents_territorial_t'] / 1e3)} kt) {C('ukghg')}; and "
     f"that share plus the catchment herds' enteric and manure emissions ({f0(LF['baselines']['residents_plus_cattle_t'] / 1e3)} kt). Results "
     f"are given for full deployment, without seaweed approval, and for limited adoption (half of homes, farms and drying customers). "
     f"Every reduction is an avoided emission against a stated counterfactual — current heating fuels, the existing petrol and diesel "
     f"fleet, fossil-fired drying, untreated manure storage, unmonitored digesters, red diesel and imported feed — not a removal of carbon "
     f"from the atmosphere, and none is yet committed. The measures are grouped by evidence: tier A, proven technology with no regulatory or "
     f"market dependence beyond household take-up (home heat, washing water, vehicle replacement, leak detection, circular feed); tier B, "
     f"dependent on markets and partners (drying contracts, digesters and biomethane, farm and residents' HVO); and tier C, dependent on "
     f"regulatory approval (Asparagopsis). To avoid double counting, farm fuel is counted only through the all-farm HVO measure, residents' "
     f"HVO covers only diesel use outside the replaced vehicle fleet, biomethane excludes biogas used by the block, and the digester credit "
     f"counts avoided storage methane separately from the gas it displaces.")

head("2.6 25-year costs, jobs and GPU economics", 2)
para(f"Costs are accounted over the {H}-year life of the wind and solar contracts in 2025 prices, undiscounted and at a {pc(P.COSTS['discount_rate'], 0)} "
     f"discount rate, for the energy supply, the community programme and vehicle finance. Jobs are estimated from staffing ratios for each "
     f"activity (data-centre operations 1.7 per MW of IT; greenhouses 15 per ha; aquaculture 0.09 per tonne; seaweed 5 per ha; and so on), "
     f"and are reported in two groups: data-centre and energy jobs, comparable with the operational jobs announced for Cambois, and "
     f"community-programme jobs. "
     f"The IT capacity is filled with GB300 NVL72 racks (135 kW and US$6.0 million per 72 GPUs, 2.06 kW per GPU with non-rack IT) or Vera "
     f"Rubin NVL72 racks (220 kW, US$8.45 million, the midpoint of published estimates {C('vr')}). Fleets are refreshed every four years with "
     f"20% residual value; prices fall US$1/GPU-h a year within a generation and restart either at the same level or 15% lower. Starting "
     f"prices are US$5.87 (reservation) and US$8.98 (on-demand) per GPU-hour {C('amc')}, with a 10% rack-scale premium; 85% of hours are sold; "
     f"facility capital is US$10 million/MW; the discount rate is 9% and UK corporation tax 25%. Digital Gardens' cash flows include the "
     f"community programme and vehicle finance. Because NPV is linear in a label premium, the premium that equalises Digital Gardens with a "
     f"Cambois-type twin is solved exactly.")

head("2.7 Reproducibility", 2)
para("All calculations are in the accompanying archive: power_247.py (hourly dispatch, portfolio search; `design` mode for the design case, "
     "outage tests and wind-yield replays), design_trajectory.py and trajectory.py (GB decarbonisation path and operating-rule comparison), "
     "heat_community.py (heat, drying, rivers, food, feed, seaweed, digesters, community ledger, vehicles and jobs), design_econ.py and "
     "compare_econ.py (comparators, emissions, water and GPU economics), figures.py and build_manuscript.py. validate.py asserts more than a "
     "hundred balances and results, including that the design is the least-cost feasible portfolio, heat balances at every node, food "
     "quantities, outage autonomy in every year and the ledger arithmetic. Two downloaders reproduce the ERA5 and grid inputs.")

# ================================================================ 3 results
head("3. Results", 1)
head("3.1 Digital Gardens versus QTS Cambois and Stargate UK", 2)
rows = [["Measure", "Digital Gardens (modelled design case)", "Modelled grid twin at the same IT (from Cambois / Stargate UK announced characteristics)"],
        ["IT load", f"{f1(P.NETWORK['it_mw'])} MW at eight nodes", f"{f1(P.NETWORK['it_mw'])} MW (Cambois full build 720 MW; Stargate UK 16.5–63.9 MW)"],
        ["Supply", f"{f0(S['wind_mw'])} MW wind, {f0(S['solar_mwp'])} MWp solar, {f0(S['battery_mwh'])} MWh battery, grid, 110 MW renewable-fuel block on grid failure",
         "GB grid with annual certificates"],
        ["Own wind, solar and battery, hourly", f"{pc(S['self_supply'])} (2018–2025); {pc(six['min'])} in the worst of 16 years", "none"],
        ["Electricity sold to the grid", f"{f0(S['export_gwh'])} GWh/yr", "none"],
        ["Grid failure", f"{f1(ISL_D)} days at full load on battery and stored fuel over a double-circuit 33 kV island network (no deliveries; conditional on protection and stability studies)", "not reported"],
        ["Surplus offtake", f"£{f1(XS['central: all surplus at hourly price']['energy_gbp_mwh'])}/MWh at hourly prices; £{f1(XS['merchant PPA: 90% of hourly price, 5% constraint curtailment']['energy_gbp_mwh'])}–{f1(XS['export capped at 200 MW, merchant PPA terms']['energy_gbp_mwh'])} under merchant terms and export caps", "—"],
        ["With unscaled ERA5 winds", f"{f0(RO['wind_mw'])} MW wind, {f0(RO['solar_mwp'])} MWp solar, {f0(RO['battery_mwh'])} MWh for {pc(RO['self_supply'])}; £{f1(RO['cost_full'])}/MWh", "—"],
        ["Energy cost, £/MWh consumed", f1(S["cost_full"]), f1(d["comparator"]["energy_gbp_mwh"])],
        ["Delivered cost incl. network and policy charges", f"£{f1(EC['dg_delivered'])}/MWh", f"£{f1(EC['cambois_delivered'])}/MWh (with the full £14/MWh discount)"],
        ["Operational emissions, 2018–2025 grid", f"{f1(DGLCA['op_t'] / 1e3)} kt/yr ({f0(DGLCA['op_g'])} g/kWh)", f"{f0(twin['op_t'] / 1e3)} kt/yr ({f0(GB)} g/kWh)"],
        ["Life-cycle emissions, 2018–2025 grid", f"{f1(DGLCA['lca_t'] / 1e3)} kt/yr ({f0(DGLCA['lca_g'])} g/kWh)", f"{f0(twin['lca_t'] / 1e3)} kt/yr ({f0(GRLCA['lca_g'])} g/kWh)"],
        ["Emissions 2027–2051, operational / life cycle", f"{f0(CUM['dg_op_kt'])} / {f0(CUM['dg_lca_kt'])} kt", f"{f0(CUM['twin_op_kt'])} / {f0(CUM['twin_lca_kt'])} kt"],
        ["Host-community avoided emissions (potential)", f"{f0(LEDW)} kt CO₂e/yr adoption-weighted; {f0(LEDL)}–{f0(LED)} kt limited to full", "none committed"],
        ["Recoverable heat used", f"{pc(th['used_share_of_recoverable'], 0)}; {pc(CD['used_share_of_recoverable'], 0)} with continuous drying", "none committed (district heating to be explored)"],
        ["Cooling water", "0 (closed loop to river or dry coolers)", "0 (waterless free-cooling chillers)"],
        ["Fresh produce and seafood", f"{f0(fa['veg_t'])} t and {f0(fa['seafood_t'])} t a year", "none"],
        ["Data-centre and energy jobs", f"{JB['dg_data_centre_energy']} ({f1(JB['dg_data_centre_energy_per_mw'])} per MW of IT)", f"Cambois: 400 operational for 720 MW ({f2(JB['cambois_per_mw'])} per MW)"],
        ["Community-programme jobs", f"{JB['dg_community']}", "none reported"]]
table(rows, "Table 2. Digital Gardens and a modelled grid-supplied twin of the same IT load (per year unless stated; 2025 price level).")
para(f"All comparator figures below are for modelled twins built from the announced characteristics in Table 1; they are not "
     f"observed performance. At the same {f1(P.NETWORK['it_mw'])} MW of IT, a grid twin would have emitted {f0(twin['op_t'] / 1e3)} kt CO₂ a year at the "
     f"2018–2025 GB intensity. Digital Gardens imports {f0(S['import_gwh'])} GWh a year, {pc(1 - S['self_supply'], 0)} of its consumption, "
     f"and emits {f1(DGLCA['op_t'] / 1e3)} kt operationally, {pc(1 - DGLCA['op_t'] / twin['op_t'], 0)} less. Its imports fall in the hours "
     f"when wind and solar are short, which are dirtier than average: they carry {f0(dt['import_weighted_g_kwh_2018_2025'])} g/kWh against "
     f"the grid mean of {f0(GB)} g/kWh. On the life-cycle basis, which adds the embodied emissions of the wind, solar and battery it consumes, "
     f"it emits {f1(DGLCA['lca_t'] / 1e3)} kt against {f0(twin['lca_t'] / 1e3)} kt. At Cambois' full 720 MW the grid campus would use "
     f"{f2(cam['twh'])} TWh a year, {f2(cam['op_mt'])} Mt CO₂ at the 2018–2025 intensity and {f2(cam['cum_lca_mt'])} Mt on the life-cycle "
     f"basis over 2027–2051; Stargate UK's 8,000 and 31,000 GPUs correspond to {f0(sg['gpus_initial']['op_kt'])} and "
     f"{f0(sg['gpus_potential']['op_kt'])} kt a year. Water does not separate the designs: Cambois' chillers and Digital Gardens' closed "
     f"loops both evaporate nothing. What separates them is hourly supply, resilience, heat and the host communities. Relative to a grid "
     f"campus of the same IT and to the communities' current fuels, vehicles and farm practices, the network and its programme lower "
     f"emissions by {f0(twin['lca_t'] / 1e3 - DGLCA['lca_t'] / 1e3 + LEDL)}–{f0(twin['lca_t'] / 1e3 - DGLCA['lca_t'] / 1e3 + LED)} kt a year "
     f"on the life-cycle basis: {f0(twin['lca_t'] / 1e3 - DGLCA['lca_t'] / 1e3)} kt from supply and {f0(LEDL)}–{f0(LED)} kt of potential "
     f"avoided emissions in the host communities ({f0(LEDW)} kt in the adoption-weighted central case). The avoided emissions exceed the network's own {f1(de['net']['dg_lca_kt_yr'])} kt a year "
     f"under full deployment, but they are reductions against counterfactuals, not removals, and are reported separately from the "
     f"network's own emissions.")
figure("Figure_1_head_to_head", "Fig. 1. (a) Emissions intensity of supply on the GB decarbonisation path for a grid campus and for Digital Gardens, "
       "life-cycle (solid) and operational (dotted). (b) Cumulative life-cycle emissions 2027–2051 at the same IT load, with host-community "
       "avoided emissions over the same period under limited adoption and the further amount under full deployment (reported separately; "
       "they are not carbon removals).")

head("3.2 Sizing renewables and storage to sell back and stand alone", 2)
rows = [["Target", "Wind MW", "Solar MWp", "Battery MWh", "Self-supply", "Worst year", "Output/use", "Sold GWh",
         "Import GWh", "£/MWh full", "£/MWh capped", "£/MWh none"]]
for f in d["frontier"]:
    rows.append([pc(f["target"], 0), f0(f["wind_mw"]), f0(f["solar_mwp"]), f0(f["battery_mwh"]), pc(f["self_supply"]), pc(f["self_supply_min"]),
                 f2(f["gen_ratio"]), f0(f["export_gwh"]), f0(f["import_gwh"]), f1(f["cost_full"]), f1(f["cost_capped"]), f1(f["cost_zero"])])
landscape(True)
table(rows, "Table 3. Least-cost portfolios by hourly self-supply target, battery ≤ 400 MWh and output ≤ 2× consumption, 2018–2025 "
      "(energy cost in £/MWh consumed, including the standby block and private network; non-commodity charges excluded). The 80% row is "
      "the design case.", size=6.8)
landscape(False)
para(f"Grid power with annual certificates costs £{f1(d['comparator']['energy_gbp_mwh'])}/MWh at 2025 prices "
     f"(£{f1(d['comparator']['energy_hist'])} at observed 2018–2025 prices). Because surplus can be sold, the cheapest portfolios are large: "
     f"half of consumption is met hour by hour by {f0(d['frontier'][0]['wind_mw'])} MW of wind and {f0(d['frontier'][0]['solar_mwp'])} MWp of "
     f"solar at £{f1(d['frontier'][0]['cost_full'])}/MWh, slightly below the grid's cost, because solar at £65/MWh sells at summer wholesale prices "
     f"close to what it costs (Fig. 2). Raising the target adds wind and then storage; the battery first appears at 75%, and the 80% design "
     f"needs the full {f0(S['battery_mwh'])} MWh. The design contracts {f2(S['gen_ratio'])} times its consumption, sells "
     f"{f0(S['export_gwh'])} GWh a year for £{f1(S['export_revenue'] / 1e6)} million, imports {f0(S['import_gwh'])} GWh and curtails "
     f"{f0(S['curtail_gwh'])} GWh; it costs £{f1(S['cost_full'])}/MWh, £{f1(S['cost_full'] - d['comparator']['energy_gbp_mwh'])} more than grid "
     f"power, or £{f1(S['cost_hist'])} at observed prices. The result depends on the value of the surplus: if it earns no more than its contract "
     f"price the cost is £{f1(S['cost_capped'])}/MWh, and if it earns nothing £{f1(S['cost_zero'])}. The surplus is mostly midday solar, "
     f"so it already sells below the average price: its capture price is £{f1(S['export_capture_gbp_mwh'])}/MWh against a mean of "
     f"£{f1(S['mean_price_gbp_mwh'])}/MWh, a capture ratio of {pc(CAPR, 0)}. If further solar build-out erodes that value so that the "
     f"surplus earns 80% or 60% of the hourly price, the energy cost rises to £{f1(EXV['0.8']['energy_gbp_mwh'])} or "
     f"£{f1(EXV['0.6']['energy_gbp_mwh'])}/MWh. A long-term offtake contract for the surplus is therefore as important to the design as "
     f"the purchase contract for the wind and solar. The {f0(S['solar_mwp'])} MWp of solar would "
     f"need on the order of {f0(S['solar_mwp'] * SOLAR_HA_PER_MWP)} ha at {SOLAR_HA_PER_MWP} ha/MWp, so it would be contracted from projects "
     f"across the region rather than built at the nodes. For comparison, the website portfolio (267 MW wind, 89 MWp solar, 250 MWh battery) "
     f"supplies {pc(w0['cfe_mean'], 0)} hour by hour, and a fossil-free-first rule that runs the block before importing reaches 100% at "
     f"£{f1(frp[1.0]['cost_gbp_mwh'])}/MWh, burning {f1(OLD['fossil-free']['mean_fuel_ml'])} ML of renewable fuel a year.")
rows = [["Surplus offtake case", "Sold, GWh", "Curtailed, GWh", "Surplus value, £m", "Energy cost, £/MWh", "Premium, US$/GPU-h"]]
for k, x in XR.items():
    rows.append([k[0].upper() + k[1:], f0(x["export_gwh"]), f0(x["curtailed_gwh"]), f1(x["export_value_gbp"] / 1e6), f1(x["energy_gbp_mwh"]), f2(XS[k]["premium"])])
table(rows, "Table 4. Design portfolio re-dispatched under surplus offtake terms and export caps, 2018–2025 (2025 price level; premium for "
      "GB300 at on-demand prices).", size=7.5)
para(f"Because the surplus peaks at {f0(XR['central: all surplus at hourly price']['peak_export_mw'])} MW at midday in summer, an export cap "
     f"bites only on a few hundred hours: a 600 MW cap curtails {f0(XR['export capped at 600 MW']['curtailed_gwh'] - XR['central: all surplus at hourly price']['curtailed_gwh'])} GWh "
     f"more and adds £{f1(XS['export capped at 600 MW']['energy_gbp_mwh'] - XS['central: all surplus at hourly price']['energy_gbp_mwh'])}/MWh. "
     f"Merchant offtake terms matter more: a PPA at 90% of the hourly price with 5% constraint curtailment adds "
     f"£{f1(XS['merchant PPA: 90% of hourly price, 5% constraint curtailment']['energy_gbp_mwh'] - XS['central: all surplus at hourly price']['energy_gbp_mwh'])}/MWh, "
     f"and with a 200 MW cap the cost reaches £{f1(XS['export capped at 200 MW, merchant PPA terms']['energy_gbp_mwh'])}/MWh. The contracted "
     f"plants' own connection charges and transmission use-of-system charges are part of the CfD-level strike prices paid for their output "
     f"and are not charged again.")
figure("Figure_2_cost_of_self_supply", "Fig. 2. Energy cost against hourly self-supply for all portfolios with a battery of at most 400 MWh and output "
       "of at most twice consumption, the least-cost frontier with surplus sold at the hourly price and with surplus capped at the contract "
       "price, the website portfolio and the design case (2018–2025 weather and grid years, 2025 price level).")
para(f"The block is the last resort. In normal operation the grid covers every shortfall, so the block runs only for its tests and burns "
     f"{f2(de['block']['test_fuel_ml'])} ML of HVO a year. When the grid fails, the contracted wind and solar plants, which are remote and "
     f"connected only through the public grid, are lost to the nodes along with grid imports. The islanded nodes then run on the battery and "
     f"the block, fed over the private network from Hexham. At full load the busiest circuit (Hexham–Chollerford) carries "
     f"{pc(ISL['max_loading'], 0)} of its rating with both circuits in service and {pc(ISL['n1_worst_loading'], 0)} with one out; the lowest "
     f"voltage, at Falstone, is {f2(ISL['min_voltage_pu'])} p.u. ({f2(ISL['n1_min_voltage_pu'])} p.u. in the worst single-circuit outage), "
     f"inside the ±6% limit, and losses are {f1(ISL['losses_mw'])} MW. Losing one of the two turbine units leaves "
     f"{f0(ISL['gt_n1']['remaining_mw'])} MW against {f1(ISL['total_load_mw'])} MW of load: the battery covers the "
     f"{f0(ISL['gt_n1']['shortfall_mw'])} MW gap for {f1(ISL['gt_n1']['battery_duration_at_rated_power_h'])} hours, after which about "
     f"{pc(ISL['gt_n1']['it_curtailment_share'], 0)} of the IT load must be curtailed until the unit returns. With both units available the full "
     f"{f1(d['load_mw'])} MW can be carried for {f1(ISL_D)} days without fuel deliveries, with the tri-mix supplying the last {f0(d['outage'][0]['trimix_hours'])} hours (Fig. 3b). Road deliveries of HVO during an "
     f"outage, or shedding the community load, extend this; neither is assumed. Only if the contracted plants were connected to the nodes by "
     f"private wire, which is not part of the design, would the network carry full load for the whole 30 days tested in every weather year.")
figure("Figure_3_low_wind_fortnight", "Fig. 3. Hourly supply of the design portfolio in the lowest-wind fortnight of 2021: (a) in normal "
       "operation, with the grid filling every shortfall; (b) with a complete grid outage for the same fortnight, the islanded nodes running "
       "on the battery and the block, with the HVO tank level (solid) and, for comparison, the tank level if the contracted renewables were "
       "also islanded (dashed); dotted line: one-third tri-mix threshold.")

head("3.3 Dependence on wind yield and weather", 2)
para(f"With unscaled ERA5 winds the fleet capacity factor is {pc(WT['raw']['fleet_cf'])} and the design portfolio supplies "
     f"{pc(RAW['selected_at_raw']['self_supply'])} of consumption, short of the 80% target; the most any portfolio within the battery and "
     f"output limits can reach is {pc(RAW['max_self_supply'])}. Re-optimised for unscaled winds, the least-cost portfolio that meets 80% has "
     f"{f0(RO['wind_mw'])} MW of wind, {f0(RO['solar_mwp'])} MWp of solar and {f0(RO['battery_mwh'])} MWh of battery and costs "
     f"£{f1(RO['cost_full'])}/MWh (£{f1(RO['cost_capped'])} with surplus capped at the contract price). The central case scales speeds by "
     f"{pc(WT['0.3']['scale'] - 1, 0)} to a 30% fleet capacity factor, which lies between the GB onshore fleet's measured 25.3% for "
     f"2020–2024 and the 36% that DESNZ assumes for new projects {C('ruk')}; the unscaled reanalysis is itself close to the measured fleet "
     f"value, which is why the correction is small. Over sixteen weather years the design supplies {pc(six['mean'])} of consumption on "
     f"average and {pc(six['min'])} in the worst year; at the fleet's 25.3% it supplies {pc(WT['0.253']['mean'])} and at 36% "
     f"{pc(WT['0.36']['mean'])} (Fig. 4). The grid makes up any difference, so wind yield changes cost and emissions but not reliability "
     f"in normal operation. Turbine-site measurement is still required before any procurement.")
figure("Figure_4_wind_yield", "Fig. 4. Sixteen-year mean and worst-year hourly self-supply of the design portfolio at different wind fleet "
       "capacity factors.", width=12)

head("3.4 Emissions per GW of IT on the GB decarbonisation path", 2)
rows = [["Grid level", "Design", "Operational, g/kWh", "Life cycle, g/kWh", "Operational, Mt/GW-yr", "Life cycle, Mt/GW-yr"]]
for lvl in ("2018-2025 observed", "2025", "2030 (Clean Power 2030)", "2035 (CCC)"):
    for k, v in TAB[lvl].items():
        rows.append([lvl, k, f1(v["op_g"]), f1(v["lca_g"]), f"{v['op_mt_gw']:.3f}", f"{v['lca_mt_gw']:.3f}"])
table(rows, "Table 4. Emissions intensity of supply and emissions per GW of IT per year (data-centre share of Digital Gardens' load).", size=7.5)
t30 = TAB["2030 (Clean Power 2030)"]; t35 = TAB["2035 (CCC)"]
para(f"Per GW of IT, a grid campus emits {f2(GRLCA['op_mt_gw'])} Mt CO₂ a year at the 2018–2025 intensity and Digital Gardens "
     f"{f2(DGLCA['op_mt_gw'])} Mt operationally. At the Clean Power 2030 level of 50 g/kWh Digital Gardens is "
     f"{f0(t30['Digital Gardens']['op_g'])} g/kWh operationally and {f0(t30['Digital Gardens']['lca_g'])} g/kWh on the life-cycle basis, "
     f"against {f0(t30['Grid campus']['op_g'])} and {f0(t30['Grid campus']['lca_g'])} g/kWh. On the 2035 path of 10 g/kWh the order reverses "
     f"on the life-cycle basis — {f0(t35['Digital Gardens']['lca_g'])} against {f0(t35['Grid campus']['lca_g'])} g/kWh — because the embodied "
     f"emissions of a large solar fleet then exceed those of a nearly decarbonised grid (Fig. 1a). Over 2027–2051 the design still emits "
     f"{pc(1 - CUM['dg_lca_kt'] / CUM['twin_lca_kt'], 0)} less than the grid campus on the life-cycle basis ({f0(CUM['dg_lca_kt'])} against "
     f"{f0(CUM['twin_lca_kt'])} kt) and {pc(1 - CUM['dg_op_kt'] / CUM['twin_op_kt'], 0)} less operationally. The dispatch order matters: "
     f"the fossil-free-first rule, which burns renewable fuel at {f0(tr['fuel_g_kwh'])} g/kWh on the life-cycle basis before importing, would "
     f"emit {f0(OLD['fossil-free']['dg_lca_kt'])} kt over the same period, more than the grid campus, because its fuel is dirtier than the "
     f"grid planned for 2030. Using the grid before the block, as the design does, avoids that. The advantage depends on how fast the grid "
     f"decarbonises: on the slower path the design emits {f0(GPS['slower (100 g 2030, 50 g 2035, 25 g 2040)']['dg_lca_kt'])} kt against "
     f"{f0(GPS['slower (100 g 2030, 50 g 2035, 25 g 2040)']['twin_lca_kt'])} kt over 2027–2051, and on the faster path "
     f"{f0(GPS['faster (30 g 2030, 5 g 2035)']['dg_lca_kt'])} kt against {f0(GPS['faster (30 g 2030, 5 g 2035)']['twin_lca_kt'])} kt, "
     f"when the two are nearly equal because the embodied emissions of the large solar fleet dominate.")

head("3.5 Heat reuse and thermal efficiency", 2)
rows = [["Node", "IT MW", "Recov.", "Homes", "Food", "Seaweed", "Digest.", "Drying", "River", "Dry cool.", "Used"]]
for n in hc["heat"]["nodes"]:
    rows.append([n["node"], f1(n["it_mw"]), f1(n["recoverable_gwh"]), f1(n["homes_gwh"]), f1(n["greenhouse_gwh"] + n["ras_gwh"]), f1(n["seaweed_gwh"]),
                 f1(n["digester_gwh"]), f1(n["drying_gwh"]), f1(n["river_gwh"]), f1(n["dry_cooler_gwh"]), pc(n["used_share"], 0)])
rows.append(["Total", f1(P.NETWORK["it_mw"]), f1(th["recoverable_gwh"]), f1(th["homes_gwh"]), f1(th["greenhouse_gwh"] + th["ras_gwh"]), f1(th["seaweed_gwh"]),
             f1(th["digester_gwh"]), f1(th["drying_gwh"]), f1(th["river_gwh"]), f1(th["dry_cooler_gwh"]), pc(th["used_share_of_recoverable"], 0)])
landscape(True)
table(rows, "Table 5. Annual fate of recoverable IT heat by node, GWh (node-by-node hourly matching, 2010–2025 weather).", size=6.8)
landscape(False)
para(f"Hot-water lines to all {f0(pg['connected_households'])} households, with home heat pumps for the last few degrees, meet every home's "
     f"space heating, hot water, washing and cleaning in every hour of the sixteen years: {f1(th['homes_gwh'])} GWh a year, about "
     f"{f1(hc['heat']['nodes'][6]['heat_per_household_mwh'])} MWh per household in Hexham and {f1(hc['heat']['nodes'][0]['heat_per_household_mwh'])} "
     f"MWh in Falstone, for {f1(th['home_hp_el_gwh'])} GWh of heat-pump electricity. But homes, greenhouses, aquaculture, seaweed and "
     f"digesters together use only {pc(th['used_share_without_drying'], 0)} of the {f0(th['recoverable_gwh'])} GWh recoverable, because "
     f"4.46 kW of IT per resident produces about five times a household's heat demand. Drying raises use to "
     f"{pc(th['used_share_of_recoverable'], 0)}, with the wood-chip pre-drying at Hexham taking "
     f"{f0(hc['heat']['contracts_served_gwh']['Wood-chip pre-drying for panel board (Hexham)'])} of the {f0(th['drying_gwh'])} GWh and the "
     f"bartered farm drying {f1(hc['heat']['contracts_served_gwh']['Grain drying for local farmers (bartered for manure and crop residues)'] + hc['heat']['contracts_served_gwh']['Hay, haylage, straw and farm woodchip drying (bartered)'])} GWh. "
     f"Barrasford, Chollerford and Corbridge, with little drying demand, use about "
     f"{pc(sum(hc['heat']['nodes'][i]['used_share'] for i in (3, 4, 7)) / 3, 0)} of their heat. Connecting 80% of households instead of all lowers use to "
     f"{pc(HS['connected 80%']['used_share_of_recoverable'], 0)}.")
rows = [["Case", "Recoverable heat used", "IT heat used", "Energy reuse factor", "Useful-energy efficiency", "Rejected, GWh"]]
for lab, s_ in (("Design (seasonal and year-round contracts)", th), ("80% of households connected", HS["connected 80%"]),
                ("Drying contracts doubled", HS["drying x2"]), ("Seaweed for the whole North East herd", HS["seaweed for the whole North East herd"]),
                ("Continuous drying contracts at every node", CD)):
    rows.append([lab, pc(s_["used_share_of_recoverable"], 0), pc(s_["used_share_of_it_heat"], 0), pc(s_["erf"], 0), f2(s_["useful_energy_efficiency"]),
                 f0(max(s_["river_gwh"], 0) + max(s_["dry_cooler_gwh"], 0))])
table(rows, "Table 6. Thermal efficiency of the network. Useful-energy efficiency is (IT electricity + heat used) / facility electricity.")
cd_water_kt = CD['continuous_contracts_gwh'] * 1e6 / 1.3 / 1e6
para(f"The continuous-drying case is an upper bound, not an identified market. It assumes year-round drying customers at every node "
     f"taking the {f0(CD['continuous_contracts_gwh'])} GWh that would otherwise be rejected — about {f0(cd_water_kt)} kt of water removed a "
     f"year at 1.3 kWh/kg, more than the identified contracts combined and concentrated at Barrasford, Chollerford, Corbridge and Haydon "
     f"Bridge, where no such customer has been identified. With it the network would use all of its recoverable heat: {pc(CD['used_share_of_it_heat'], 1)} of IT heat, the "
     f"ceiling set by 85% capture and 15% distribution loss, an energy reuse factor of {pc(CD['erf'], 0)}, and a useful-energy efficiency of "
     f"{f2(CD['useful_energy_efficiency'])}, against {f2(th['useful_energy_efficiency'])} in the design case: each unit of facility electricity delivers {f2(1 / P.NETWORK['pue'])} units of computing and {f2(CD['erf'])} units of useful heat. No river discharge or dry cooler would then be "
     f"needed. If those customers dry with oil or gas today, the contracts would displace {f0(CD['fossil_drying_displaced_t'] / 1e3)} kt "
     f"CO₂e a year of drying fuel, against {f1(LF['rows']['Drying contracts (fossil-fired drying displaced)'] / 1e3)} kt in the design case. "
     f"The design case, with the drying demand actually identified, is the basis for every other result.")
figure("Figure_5_heat_by_node", "Fig. 5. Share of recoverable IT heat used and rejected at each node after hourly matching (2010–2025 weather), "
       "with the annual recoverable total.")
figure("Figure_6_monthly_heat", "Fig. 6. Monthly use and rejection of recoverable heat, all nodes.", width=13)

head("3.6 Food, the circular feed loop and red seaweed", 2)
rows = [["Flow", "t per year"],
        ["Fresh produce (146 kg per resident)", f0(fa["veg_t"])], ["Seafood, live weight (46 kg per resident)", f0(fa["seafood_t"])],
        ["  of which finfish / prawns", f"{f0(fd['finfish_t'])} / {f0(fd['prawn_t'])}"],
        ["Feed required: fish / prawns", f"{f0(fd['feed_fish_t'])} / {f0(fd['feed_prawn_t'])}"],
        ["Prawn meal fed to fish", f1(fd["prawn_meal_t"])], ["Fish meal fed to prawns", f1(fd["fish_meal_t"])],
        ["Greenhouse waste used", f0(fd["greenhouse_waste_t"])], ["  as direct green feed / black soldier fly meal", f"{f0(fd['greens_direct_t'])} / {f1(fd['bsf_meal_t'])}"],
        ["Local cereals, pulses and rapeseed meal", f0(fd["local_plant_t"])],
        ["Local share of feed: fish / prawns / total", f"{pc(fd['local_share_fish'], 0)} / {pc(fd['local_share_prawn'], 0)} / {pc(fd['local_share_total'], 0)}"],
        ["Imported feed remaining", f0(fd["imported_feed_t"])],
        ["Dissolved nitrogen in effluent", f1(fd["n_dissolved_t"])],
        ["Seaweed the effluent can support, dry weight", f0(fd["seaweed_capacity_t_dw"])],
        ["Seaweed needed for catchment cattle / whole NE herd, dry weight", f"{f0(fa['asparagopsis_t_dw'])} / {f0(hc['heat_north_east']['facts']['asparagopsis_t_dw'])}"],
        ["Seaweed tanks for catchment / whole NE herd, ha", f"{f1(fa['asparagopsis_ha'])} / {f1(hc['heat_north_east']['facts']['asparagopsis_ha'])}"]]
table(rows, "Table 7. Food, feed and seaweed flows.")
para(f"The feed loop supplies {pc(fd['local_share_total'], 0)} of the aquaculture's {f0(fd['feed_fish_t'] + fd['feed_prawn_t'])} t of feed "
     f"from local sources and saves {f1(fd['credit_t'] / 1e3)} kt CO₂e a year against imported feed. Prawn and fish meals are small, "
     f"{f0(fd['prawn_meal_t'])} t and {f0(fd['fish_meal_t'])} t, because by-products are a fraction of a modest harvest; most of the local "
     f"share comes from greenhouse waste, insect meal and Tyne valley crops. The effluent's nitrogen could grow "
     f"{pc(fd['seaweed_capacity_t_dw'] / fa['asparagopsis_t_dw'] - 1, 0)} more seaweed than the catchment herds need, so the fish and prawn "
     f"farms can supply them with nutrients to spare; supplying the whole North East herd would need "
     f"{f0(hc['heat_north_east']['facts']['asparagopsis_t_dw'])} t, slightly more than the effluent supports, and "
     f"{f1(hc['heat_north_east']['facts']['asparagopsis_ha'])} ha of tanks taking {f0(HS['seaweed for the whole North East herd']['seaweed_gwh'])} GWh "
     f"of server heat.")

head("3.7 Host-community greenhouse-gas reductions", 2)
rows = [["Measure (counterfactual)", "Tier", "Full deployment", "Full, no seaweed approval", "Limited adoption", "Whole North East farms and herd"]]
for t_ in "ABC":
    for k, v in LF["rows"].items():
        if TIER[k] == t_:
            rows.append([k, t_, f1(v / 1e3), f1(LN["rows"][k] / 1e3), f1(LL["rows"][k] / 1e3), f1(LNE["rows"][k] / 1e3)])
for t_, lab in (("A", "Subtotal, tier A (proven, no regulatory or market dependence)"), ("B", "Subtotal, tier B (market- and partner-dependent)"),
                ("C", "Subtotal, tier C (regulatory approval required)")):
    rows.append([lab, t_] + [f1(sum(v for k, v in X["rows"].items() if TIER[k] == t_) / 1e3) for X in (LF, LN, LL, LNE)])
rows.append(["Total", "", f1(LED), f1(LEDN), f1(LEDL), f1(LNE["total_t"] / 1e3)])
for lab, key in (("% of emissions of the activities addressed", "of_addressed_sectors"), ("% of residents' territorial emissions plus catchment cattle", "of_residents_plus_cattle")):
    rows.append([lab, ""] + [pc(x["percent"][key], 0) for x in (LF, LN, LL, LNE)])
landscape(True)
table(rows, "Table 8. Potential host-community avoided emissions, kt CO₂e per year, by evidence tier, against current practice in each "
      "activity (none committed; avoided emissions, not removals).", size=7.5)
landscape(False)
asp = LF["rows"]["Free red seaweed (Asparagopsis) for dairy and beef cattle"]
para(f"Weighting each measure by its likelihood of delivery — 75% for tier A, 50% for tier B and 25% for tier C, an assumption reflecting "
     f"household uptake, partner and market risk, and the uncertainty of approval — gives a central estimate of {f1(LEDW)} kt CO₂e a year "
     f"({pc(LW['percent']['of_addressed_sectors'], 0)} of the emissions addressed), close to the limited-adoption case; full deployment is an "
     f"upper bound. Tier A measures, which depend only on household take-up of proven technology, account for {f1(TIER_SUM['A'])} kt a year at full deployment; "
     f"market- and partner-dependent measures for {f1(TIER_SUM['B'])} kt; and the seaweed, which needs regulatory approval, for "
     f"{f1(TIER_SUM['C'])} kt. Under full deployment the measures could avoid {f1(LED)} kt CO₂e a year, {f1(LED * 1e3 / fa['population'])} t per resident: "
     f"{pc(LF['percent']['of_addressed_sectors'], 0)} of the emissions of the activities they address and "
     f"{pc(LF['percent']['of_residents_plus_cattle'], 0)} of residents' territorial emissions plus those of the catchment cattle. Without "
     f"seaweed approval the cut is {f1(LEDN)} kt ({pc(LN['percent']['of_addressed_sectors'], 0)}), and with limited adoption {f1(LEDL)} kt "
     f"({pc(LL['percent']['of_addressed_sectors'], 0)}). Home heating and washing ({f1((LF['rows']['Home heating and hot water through district loops and home heat pumps'] + LF['rows']['Hot-fill washing and cleaning water']) / 1e3)} kt) "
     f"and vehicle replacement ({f1(LF['rows']['Household vehicles replaced by battery-electric and plug-in hybrid vehicles'] / 1e3)} kt) are "
     f"the largest measures, followed by drying ({f1(LF['rows']['Drying contracts (fossil-fired drying displaced)'] / 1e3)} kt) and free "
     f"seaweed ({f1(asp / 1e3)} kt), which cuts the catchment herds' enteric methane by {pc(LF['asp_enteric_cut_share'], 0)} "
     f"({f0(LF['asp_ch4_t'])} t CH₄). Leak detection saves {f1(LF['rows']['Methane-leak detection on digesters and upgraders'] / 1e3)} kt "
     f"({f0(LF['leak_ch4_t'])} t CH₄) for £{f0(pg['capex']['leak_detection'] / 1e3)} thousand of capital, the most cost-effective measure; "
     f"digesters supply {f1(LF['biomethane_gwh'])} GWh of biomethane. Extending free seaweed, digestion and the farm-fuel subsidy to the whole North East raises "
     f"the total to {f0(LNE['total_t'] / 1e3)} kt. Over 2027–2051 the potential avoided emissions total {f0(de['net']['cum_reductions_limited_kt'])}–"
     f"{f0(de['net']['cum_reductions_full_kt'])} kt (Fig. 1b), {f1(de['net']['cum_reductions_limited_kt'] / CUM['dg_lca_kt'])}–"
     f"{f1(de['net']['cum_reductions_full_kt'] / CUM['dg_lca_kt'])} times the network's own life-cycle emissions.")
figure("Figure_7_community_reductions", "Fig. 7. Potential host-community avoided emissions by measure, full deployment and limited adoption without seaweed approval.")

head("3.8 Costs over the 25-year life of the renewables", 2)
rows = [["Item", "Year 1, £m", f"{H}-year total, £m", f"Present value at {pc(P.COSTS['discount_rate'], 0)}, £m"]]
for lab, a, t25, p25 in acc_rows:
    rows.append([lab, f1(a / 1e6), f0(t25 / 1e6), f0(p25 / 1e6)])
rows.append(["Total, Digital Gardens", "", f0(TOT25 / 1e6), f0(TOTPV / 1e6)])
rows.append(["Grid campus at the same IT: delivered electricity", f1(EC["cambois_delivered"] * MWH / 1e6), f0(CAM25 / 1e6), f0(CAMPV / 1e6)])
table(rows, f"Table 9. 25-year cost account of the Digital Gardens network and community programme, 2025 prices (negative values are income). "
      f"The vehicle payment is £{f1(V['annual_finance_payment_gbp'] / 1e6)} million a year in years 1–7, 13–19 and 25.", size=8)
para(f"Over {H} years the energy supply costs £{f2(ENERGY25 / 1e9)} billion including network and policy charges, against "
     f"£{f2(CAM25 / 1e9)} billion for the grid campus's delivered electricity after the Growth Zone discount; the difference, "
     f"£{f0((ENERGY25 - CAM25) / 1e6)} million, is {pc((ENERGY25 - CAM25) / CAM25, 0)} of the comparator's bill. The community programme "
     f"adds £{f2(COMM25 / 1e9)} billion: £{f0(pg['capex_total'] / 1e6)} million of capital, mostly district heating "
     f"(£{f0(pg['capex']['district_heat'] / 1e6)} million) and home heat pumps (£{f0(pg['capex']['home_heat_pumps'] / 1e6)} million), "
     f"£{f1((pg['opex_total'] + EC['community_labour'] - pg['revenue_total']) / 1e6)} million a year net of income, and "
     f"£{f0(V['annual_finance_payment_gbp'] * len(veh_years) / 1e6)} million of vehicle finance for {f0(V['total'])} vehicles across two "
     f"fleets and the start of a third. Spread over the network's {f0(MWH * H / 1e6)} TWh of consumption, the whole programme adds "
     f"£{f0(COMM25 / (MWH * H))}/MWh. The seaweed is given free: its tanks cost £{f1(pg['capex']['seaweed_tanks'] / 1e6)} million and "
     f"£{f1(pg['opex']['seaweed'] / 1e6)} million a year, about £{f0((pg['capex']['seaweed_tanks'] / H + pg['opex']['seaweed']) / asp)} per "
     f"tonne of CO₂e avoided before staff costs.")

head("3.9 GPU rental economics and the clean-compute premium", 2)
rows = [["Product and start price", "Surplus at hourly price", "Surplus capped at contract price", "Surplus not valued", "Electricity only", "Share of start price"]]
for prod in ("GB300 NVL72", "Vera Rubin NVL72"):
    for tier in ("reservation", "on-demand"):
        a, b, c = (PR[f"{x}|{prod}|{tier}"] for x in ("full", "capped", "zero"))
        rows.append([f"{prod}, {tier}", f2(a["premium"]), f2(b["premium"]), f2(c["premium"]), f2(a["premium_electricity_only"]), pc(a["share_of_price"])])
table(rows, "Table 10. Break-even clean-compute premium against a Cambois-type twin, US$ per GPU-hour sold, recovering the electricity "
      "difference, the community programme and vehicle finance.")
para(f"Electricity delivered to Digital Gardens costs £{f1(EC['dg_delivered'])}/MWh against £{f1(EC['cambois_delivered'])} for the "
     f"Cambois-type twin, US${f2(g_on['elec_usd_gpu_h'])} per GB300 GPU-hour. The premium that recovers both the electricity difference and the "
     f"community programme is US${f2(g_on['premium'])} per GB300 GPU-hour at on-demand prices, {pc(g_on['share_of_price'])} of the start price; "
     f"electricity alone accounts for US${f2(g_on['premium_electricity_only'])}. If surplus earns only its contract price the premium is "
     f"US${f2(g_on_c['premium'])}, and if it earns nothing US${f2(g_on_z['premium'])}. Vera Rubin, with fewer GPUs per MW, needs "
     f"US${f2(r_on['premium'])}. Without a premium the business breaks even at a starting price of US${f2(EC['breakeven_start_gb300'])} per "
     f"GB300 GPU-hour. The NPV is far more sensitive to the compute market than to electricity (Fig. 8): with the premium the GB300 business "
     f"is worth US${f1(SENS['Central|on-demand|prices held each generation'] / 1e3)} bn at on-demand prices and "
     f"US${f2(SENS['Central|reservation|prices held each generation'] / 1e3)} bn at reservation prices, and each adverse case — GPU capital "
     f"38% higher, 70% or 60% of hours sold, prices 20% lower — turns the reservation case negative; all four together turn every case "
     f"negative. The break-even premium itself also rises in the adverse cases, because the community programme and the electricity "
     f"difference are spread over fewer sold hours: US${f2(ADV['Sold 70%']['premium'])} at 70% of hours sold, "
     f"US${f2(ADV['Sold 60%']['premium'])} at 60%, and US${f2(ADV['All four adverse']['premium'])} with all four adverse cases together, in "
     f"which both businesses lose money. The Growth Zone discount changes the premium little: if it ends after 2030 the premium is "
     f"US${f2(AIGZ['to 2030 only|on-demand']['premium'])}, and if it is never granted US${f2(AIGZ['none|on-demand']['premium'])}. If the "
     f"surplus electricity earns 80% or 60% of the hourly price the premium rises to US${f2(EXV['0.8']['premium'])} or "
     f"US${f2(EXV['0.6']['premium'])}. These are break-even values that make the two businesses equal in NPV; they are not evidence that "
     f"customers will pay them, which has not been measured, and no public GPU-rental contract discloses a price for verified "
     f"hourly-matched clean compute against which to compare them. All values illustrate the stated assumptions and are not forecasts.")
figure("Figure_8_gpu_npv", "Fig. 8. 25-year NPV of the Digital Gardens GB300 business with the break-even premium, by starting price, price "
       "path and adverse case.", width=14)

head("3.10 Water, heat rejection, air quality and jobs", 2)
rows = [["Activity", "Jobs"]] + [[k, str(v)] for k, v in hc["jobs"]["by_sector"].items()] + [["Total", str(hc["jobs"]["total"])]]
table(rows, "Table 11. Permanent jobs likely created by the network and community programme (screening staffing ratios).")
para(f"The jobs are not all comparable with the 400 operational jobs announced for Cambois {C('qts')}. Data-centre and energy roles — IT "
     f"operations ({JB['dg_it_ops']}) and the renewables, battery and standby generation ({JB['dg_data_centre_energy'] - JB['dg_it_ops']}) — "
     f"total {JB['dg_data_centre_energy']}, {f1(JB['dg_data_centre_energy_per_mw'])} per MW of IT against {f2(JB['cambois_per_mw'])} per MW at "
     f"Cambois, the difference reflecting eight small sites and an assumed staffing ratio rather than a measured one. The other "
     f"{JB['dg_community']} jobs belong to the community programme and have no counterpart at Cambois.")
para(f"Neither design consumes cooling water; the block's NOx-control water during tests is about {f0(de['water']['block_test_m3'])} m³ a "
     f"year. Unused heat, {f0(th['river_gwh'] + th['dry_cooler_gwh'])} GWh a year, peaks at {f1(rv['peak_total_rejected_mw'])} MW across the "
     f"eight nodes. If all of it went to the river, it would warm the Tyne at Bywell by {f2(rv['dT_at_q95_if_all_to_river'])} °C fully mixed at "
     f"Q95 flow. Under the local rule the five North Tyne nodes, on the regulated river below Kielder, use dry coolers only; Haydon Bridge "
     f"discharges to the South Tyne within its own Q95 limit (peak rise {f2(rv['peak_dT_haydon_k'])} °C); and Hexham and Corbridge share "
     f"what remains of the 1 °C budget at Bywell, halved to 0.5 °C in June–September. River exchangers then take "
     f"{pc(rv['river_share_of_rejected'], 0)} of rejected heat and dry coolers {f0(rv['dry_cooler_peak_total_mw'])} MW at peak "
     f"({f0(rv['dry_cooler_peak_by_node_mw']['Hexham'])} MW at Hexham). These are screening limits: each outfall still needs a mixing-zone "
     f"assessment, river-temperature data and an Environment Agency permit. With "
     f"the block running only for tests, its NOx emissions are about {f2(de['block']['nox_t'])} t a year. Wages for the community jobs, £{f1(EC['community_labour'] / 1e6)} million a year, are included in the costs above.")

# ================================================================ 4 discussion
head("4. Discussion", 1)
head("4.1 Selling back, standing alone and the order of dispatch", 2)
para(f"Because surplus can be sold, an AI load in Northumberland can contract roughly twice its consumption in wind and solar at a cost close "
     f"to grid power and meet four-fifths of its demand from its own supply in every hour. The last fifth is expensive to self-supply: the "
     f"80% design costs £{f1(S['cost_full'] - d['comparator']['energy_gbp_mwh'])}/MWh more than grid power, while closing the gap with "
     f"renewable fuel costs about £{f0(frp[1.0]['cost_gbp_mwh'] - d['comparator']['energy_gbp_mwh'])}/MWh more and, on the life-cycle basis, "
     f"emits more than the grid after 2030. The grid is therefore the cheaper and cleaner second resort, and the renewable-fuel block is best "
     f"kept as insurance against grid failure: {f1(ISL_D)} days of islanded operation on stored fuel, more with road deliveries, is a "
     f"resilience that grid-only campuses do not report, but it requires the private network and grid-forming controls costed here. The "
     f"design's economics rest on the price of surplus: the export credit is worth £{f1(S['cost_zero'] - S['cost_full'])}/MWh of "
     f"consumption. Long-term sale contracts for the surplus, or co-location with flexible demand, are the natural hedge. A credible label "
     f"would report the hourly self-supply share, the hourly intensity of imports, the operating rule and the community reductions "
     f"separately; the Dolphin Safe label succeeded because the claim was defined and verified, not because consumers paid much more for it "
     f"{C('dpcia', 'teisl')}.")
head("4.2 What the towns can do with the heat", 2)
para(f"The heat question is one of customers, not supply. Hot-water lines and home heat pumps can serve every household in all hours, "
     f"but homes take only {pc(th['homes_gwh'] / th['recoverable_gwh'], 0)} of the heat. Food, seaweed and digesters take a further "
     f"{pc((th['greenhouse_gwh'] + th['ras_gwh'] + th['seaweed_gwh'] + th['digester_gwh']) / th['recoverable_gwh'], 0)}. Drying is what "
     f"makes the network efficient, and the identified contracts take it to {pc(th['used_share_of_recoverable'], 0)}; continuous contracts "
     f"at every node would in principle use all recoverable heat (useful-energy efficiency {f2(CD['useful_energy_efficiency'])}), but that "
     f"demand has yet to be found. Bartering drying for manure and crop residues ties farmers into the digesters, whose "
     f"biogas also backs up the block's tri-mix.")
head("4.3 Training at a node or across nodes", 2)
para(f"Hexham's 50.6 MW of IT would hold about 24,500 GB300 GPUs, more than the 16,384 H100 GPUs used to train Llama 3.1 405B {C('llama')}; "
     f"most notable models have used 5,000–16,000 accelerators {C('epoch')}. A single node can therefore train most current models while the "
     f"others serve inference, and the nodes, all within about 45 km of each other, add well under a millisecond of fibre latency if a run "
     f"needs more than one site {C('spectrum')}. Neither single-node scheduling nor multi-site training performance is modelled here.")
head("4.4 Limitations", 2)
for lim in [
    f"Wind and solar. ERA5 at about 30 km resolution is scaled by {pc(WT['0.3']['scale'] - 1, 0)} to the central yield, and a design "
    f"re-optimised for unscaled winds is reported; {f0(S['solar_mwp'])} MWp of solar needs about {f0(S['solar_mwp'] * SOLAR_HA_PER_MWP)} ha; "
    f"turbine-site measurement and project yields are required.",
    "Surplus value. Wholesale prices are rescaled 2018–2025 shapes; a large solar build-out would depress midday capture prices further, "
    "which is why surplus at 80%, 60% and none of the hourly price is reported; the design needs a long-term offtake contract for its surplus.",
    "Growth Zone discount. The comparators receive the full £14/MWh for 25 years; the discount is an upper bound subject to eligibility and "
    "a 2030 review.",
    "Grid path. The 2030 and 2035 intensities are policy targets; if decarbonisation is slower the design's advantage grows.",
    "Outages. The island network is checked by a steady-state load flow with N-1 circuit and turbine contingencies; protection "
    "coordination, fault levels, dynamic stability with grid-forming inverters and black-start sequencing are not modelled, so the "
    "15-day autonomy is conditional on those studies. Contracted renewables are assumed unavailable during an outage.",
    "Rivers. The local rejection rule uses Q95 flows and a precautionary summer limit, not measured river temperatures or permitted "
    "discharge conditions.",
    "Renewable fuel. HVO price, sustainability certification and duty treatment for stationary power are represented by a fixed price and the "
    "RTFO average carbon intensity.",
    "Network charges. Contracted output is assumed to be sleeved through the public grid, so non-commodity charges apply to all consumption; "
    "private-wire supply would lower the delivered cost.",
    "Compute market. Enterprise willingness to pay a clean-compute premium has not been measured; GPU supply, utilisation and price dominate profit.",
    "Heat, food and community. Drying markets, heat demand, washing heat, seaweed heat demand, feed emission factors, herd sizes, vehicle "
    "ownership, adoption and staffing ratios are screening estimates; outfalls need permits; Asparagopsis is not authorised as a feed "
    "additive in Great Britain and its productivity in UK land-based tanks is unproven at scale.",
    "Comparators. Cambois and Stargate UK are represented by generic grid-supplied twins; no operating records for either were available, and "
    "QTS's renewable procurement, if any, is represented by annual certificates."]:
    p = doc.add_paragraph(lim, style="List Bullet"); p.paragraph_format.space_after = Pt(2)
    for r in p.runs: r.font.size = Pt(9.5)

# ================================================================ 5 conclusions
head("5. Conclusions", 1)
para(f"At the same {f1(P.NETWORK['it_mw'])} MW of IT in Northumberland, a Digital Gardens network that contracts {f0(S['wind_mw'])} MW of wind "
     f"and {f0(S['solar_mwp'])} MWp of solar with a {f0(S['battery_mwh'])} MWh battery supplies {pc(S['self_supply'], 0)} of its consumption "
     f"from its own renewables hour by hour, sells {f0(S['export_gwh'])} GWh a year back to the grid, and costs £{f1(S['cost_full'])}/MWh of "
     f"energy against £{f1(d['comparator']['energy_gbp_mwh'])} for grid power with certificates, provided its surplus finds a buyer at "
     f"market prices (£{f1(XS['merchant PPA: 90% of hourly price, 5% constraint curtailment']['energy_gbp_mwh'])}–"
     f"{f1(XS['export capped at 200 MW, merchant PPA terms']['energy_gbp_mwh'])}/MWh under merchant terms and export caps); with unscaled ERA5 winds the same target needs {f0(RO['wind_mw'])} MW of wind and {f0(RO['solar_mwp'])} MWp of solar "
     f"at £{f1(RO['cost_full'])}/MWh. Its renewable-fuel block runs only when the grid fails, and the islanded nodes can then carry full load "
     f"for {f1(ISL_D)} days on stored fuel over a double-circuit 33 kV network that passes a screening load-flow and N-1 check, subject "
     f"to protection and stability studies. Over 2027–2051 it emits "
     f"{pc(1 - CUM['dg_lca_kt'] / CUM['twin_lca_kt'], 0)} less than a modelled grid twin on the life-cycle basis on the policy-aligned grid "
     f"path, and almost the same if the grid decarbonises faster, and "
     f"{pc(1 - CUM['dg_op_kt'] / CUM['twin_op_kt'], 0)} less operationally. Neither design uses cooling water. Hot-water lines serve every "
     f"household; the towns use {pc(th['used_share_of_recoverable'], 0)} of recoverable heat with the drying demand identified, and all of it "
     f"only if continuous drying customers can be found at every node. The community programme — free red seaweed grown on fish- and prawn-farm effluent, "
     f"bartered drying, digesters with leak detection, circular feed, 146 kg of produce and 46 kg of seafood per resident, and a vehicle for "
     f"every household — could avoid about {f0(LEDW)} kt CO₂e a year against current practice in an adoption-weighted central case "
     f"(up to {f0(LED)} kt at full deployment), "
     f"{pc(LL['percent']['of_addressed_sectors'], 0)}–{pc(LF['percent']['of_addressed_sectors'], 0)} of the emissions it addresses, "
     f"{f0(TIER_SUM['A'])} kt of it from proven measures without regulatory or market dependence, and create about "
     f"{JB['dg_community']} community jobs alongside {JB['dg_data_centre_energy']} in computing and energy. A break-even premium of "
     f"US${f2(g_on['premium'])} per GB300 GPU-hour recovers the whole 25-year cost, although the business depends far more on GPU prices "
     f"and utilisation than on electricity. These are conditional scenarios: measured wind, contracts for the surplus, outfall permits, "
     f"seaweed approval and signed compute offtake are the conditions for these results to hold.")

for h_, t_ in [("Author contributions", "Jonathan Karl Bily: conceptualization, methodology, software, formal analysis, data curation, "
                 "writing – original draft, writing – review & editing."),
               ("Conflicts of interest", "The author conceived and promotes the Digital Gardens proposal and may have prospective financial "
                "interests. QTS Cambois and Stargate UK are separate projects; no operating records for either were available for this analysis."),
               ("Data availability", "All scripts, weather and grid inputs, derived outputs and validation tests are supplied with the submission "
                "as an archive and will be deposited in Zenodo with a persistent DOI before publication. ERA5 data are used under the Copernicus "
                "licence and Open-Meteo terms; NESO carbon-intensity data under CC BY 4.0; Elexon data under the BSC open data licence."),
               ("Use of generative AI", "During preparation of this work the author used Artificial Inventor/Synthetic Scientist V63 for code "
                "development, calculation checks, literature screening and editorial drafting. The author reviewed and edited the content and "
                "takes full responsibility for it."),
               ("Acknowledgements", "No dedicated external funding was received.")]:
    head(h_, 2); para(t_, size=9.5)

head("Notes and references", 1)
for i, k in enumerate(ORDER, 1):
    p = doc.add_paragraph(f"[{i}] {REF[k]}"); p.paragraph_format.space_after = Pt(1)
    for run in p.runs: run.font.size = Pt(8)
unused = [k for k in REF if k not in ORDER]
doc.save(MS / "Digital_Gardens_North_Tyne_vs_Cambois_Stargate_Manuscript.docx")

# ================================================================ highlights and cover letter
TOC = (f"Small AI nodes that buy twice their power in wind and solar, sell the surplus and share their heat could cut "
       f"{pc(1 - CUM['dg_lca_kt'] / CUM['twin_lca_kt'], 0)} of a grid campus's emissions in rural England.")
assert len(TOC.split()) <= 30, len(TOC.split())
dh = Document(); dh.add_heading("Broader context", 1); dh.add_paragraph(BROADER)
dh.add_heading("Table of contents entry", 1); dh.add_paragraph(TOC)
dh.add_paragraph("Graphic: FIGURES/Figure_1_head_to_head.png (to be cropped to 8 cm × 4 cm).")
dh.save(MS / "Broader_Context_and_TOC_Entry.docx")
c = Document()
for t_ in ["Jonathan Karl Bily\nIndependent Researcher, Zaragoza, Spain\njonathan@cloudwashlaundry.com", "The Editor\nEnergy & Environmental Science\nRoyal Society of Chemistry",
           "Dear Editor,",
           f"I submit the manuscript \"{TITLE}\" for consideration as an Analysis article in Energy & Environmental Science, under the "
           f"traditional subscription route.",
           "The paper compares a distributed AI computing network proposed for eight towns in Northumberland with grid-supplied AI campuses in "
           "the North East AI Growth Zone (QTS Cambois and Stargate UK) on carbon, water, energy and economics. It uses sixteen years of ERA5 "
           "weather and eight years of half-hourly GB carbon-intensity and price data to size contracted wind, solar and storage that sell "
           "surplus back to the grid, tests how long the islanded nodes can run on a battery and a renewable-fuel combined-cycle block if the grid fails, matches "
           "server heat to homes, greenhouses, aquaculture, seaweed tanks and drying customers node by node and hour by hour, and costs a "
           "host-community programme over the 25-year life of the renewables.",
           f"Three findings are of general interest. First, because surplus can be sold, a 93.5 MW AI load can meet {pc(S['self_supply'], 0)} of "
           f"its consumption from its own wind and solar hour by hour at £{f0(S['cost_full'])}/MWh, close to grid power at "
           f"£{f0(d['comparator']['energy_gbp_mwh'])}/MWh. Second, the order of dispatch decides the carbon outcome: renewable fuel used before "
           f"the grid emits more than a decarbonising GB grid, whereas held in reserve for grid failure it gives {f1(ISL_D)} days of islanded "
           f"operation and "
           f"{pc(1 - CUM['dg_lca_kt'] / CUM['twin_lca_kt'], 0)} lower life-cycle emissions than a grid campus over 2027–2051. Third, the heat "
           f"of rural AI nodes is limited by customers, not supply: the identified uses take {pc(th['used_share_of_recoverable'], 0)} of "
           f"recoverable heat, and the wider programme could avoid {f0(LEDL)}–{f0(LED)} kt CO2e a year in the host communities, reported by "
           f"evidence tier and separately from the network's own emissions.",
           "The analysis fits the journal's Analysis category: it quantifies a technological system and the policies around it — hourly "
           "renewable procurement, firm backup, waste-heat use and host-community decarbonisation — with a fully reproducible model.",
           "All code, input data and validation tests are provided. I conceived and promote the Digital Gardens proposal, and this interest is "
           "declared in the manuscript. The work has not been published and is not under consideration elsewhere.",
           "Yours sincerely,\nJonathan Karl Bily"]:
    c.add_paragraph(t_)
c.save(MS / "Cover_Letter.docx")
print("built", MS, "refs", len(ORDER), "unused", unused)
print("25-year:", round(TOT25 / 1e9, 3), "bn; energy", round(ENERGY25 / 1e9, 3), "community", round(COMM25 / 1e9, 3), "cambois", round(CAM25 / 1e9, 3))
