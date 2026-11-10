#!/usr/bin/env python3
"""Figures for the manuscript (PNG at 300 dpi and PDF). Run after power_247, trajectory, heat_community, compare_econ."""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import params as P
import power_247 as pw

FIG = P.HERE.parent / "FIGURES"; FIG.mkdir(exist_ok=True)
C1, C2, C3, C4, C5, C6, C7, C8 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False, "lines.linewidth": 2.0})


pwr = json.load(open(P.OUT / "power_247.json")); d = json.load(open(P.OUT / "design.json")); dt = json.load(open(P.OUT / "design_trajectory.json"))
hc = json.load(open(P.OUT / "heat_community.json")); de = json.load(open(P.OUT / "design_econ.json")); tr = json.load(open(P.OUT / "trajectory.json"))
SD = d["selected"]


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight"); fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight"); plt.close(fig)


def grid_lca(g):
    return g * 1.2 + 12.0


# Fig 1
fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 3.0), gridspec_kw=dict(width_ratios=[1.35, 1], wspace=0.38))
yrs = [r["year"] for r in dt["annual"]]
a.plot(yrs, [grid_lca(r["grid_g"]) for r in dt["annual"]], color=C2, label="Grid campus (Cambois / Stargate UK type)")
a.plot(yrs, [r["dg_lca_t"] / (d["annual_load_gwh"] * 1e3) * 1e3 for r in dt["annual"]], color=C1, label="Digital Gardens")
a.plot(yrs, [r["grid_g"] for r in dt["annual"]], color=C2, ls=":", lw=1.4, label="Grid campus, operational only")
a.plot(yrs, [r["dg_op_t"] / (d["annual_load_gwh"] * 1e3) * 1e3 for r in dt["annual"]], color=C1, ls=":", lw=1.4, label="Digital Gardens, operational only")
a.set_ylabel("g CO$_2$e per kWh supplied"); a.set_ylim(0, None); a.legend(fontsize=6.5, loc="upper right")
a.set_title("(a) Supply intensity on the GB grid path", loc="left", fontsize=9)
led = hc["ledger_full"]["total_t"] * 25 / 1e3; led_l = hc["ledger_limited"]["total_t"] * 25 / 1e3
labels = ["Grid campus,\nsame IT", "Digital\nGardens"]
b.bar(labels, [dt["cum"]["twin_lca_kt"], dt["cum"]["dg_lca_kt"]], color=[C2, C1], width=0.55)
b.bar(labels[1:], [-led_l], color=C6, width=0.55, label="Community reductions, limited adoption")
b.bar(labels[1:], [-(led - led_l)], bottom=[-led_l], color="white", edgecolor=C6, hatch="////", width=0.55, label="Additional with full deployment")
b.axhline(0, color=INK2, lw=0.8); b.set_ylabel("kt CO$_2$e, 2027-2051 (life cycle)")
b.legend(fontsize=6.3, loc="lower center", bbox_to_anchor=(0.5, -0.42))
b.set_title("(b) 25-year emissions", loc="left", fontsize=9)
save(fig, "Figure_1_head_to_head")

# Fig 2
z = np.load(P.OUT / "design_grid.npz"); L = d["annual_load_gwh"] * 1e3
ok = (z["E"] <= P.COSTS["battery_max_mwh"]) & (z["gen"] <= P.COSTS["sellback_limit"] * L)
fig, ax = plt.subplots(figsize=(6.2, 3.3))
ax.scatter(100 * z["cfe"][ok], z["cost_full"][ok], s=4, color="#9fc3ee", label="Portfolios (battery <= 400 MWh, output <= 2x use)")
fr = d["frontier"]
ax.plot([100 * f["self_supply"] for f in fr], [f["cost_full"] for f in fr], color=C1, marker="o", ms=4, label="Least-cost frontier, surplus at full price")
ax.plot([100 * f["self_supply"] for f in fr], [f["cost_capped"] for f in fr], color=C7, marker="^", ms=4, ls="--", label="Same portfolios, surplus capped at contract price")
w0 = pwr["website_portfolio"][0]
ax.scatter([100 * w0["cfe_mean"]], [w0["cost_gbp_mwh"]], marker="s", s=30, color=C4, zorder=5, label="Website portfolio")
ax.scatter([100 * SD["self_supply"]], [SD["cost_full"]], marker="*", s=120, color=C8, zorder=6, label="Design case")
g = d["comparator"]["energy_gbp_mwh"]; ax.axhline(g, color=C2, lw=1.5, ls="--")
ax.text(41, g - 5, f"Grid + annual certificates, £{g:.0f}/MWh", color=INK2, fontsize=7)
ax.set_xlabel("Hourly self-supply from contracted wind, solar and battery, % (2018-2025)"); ax.set_ylabel("Energy cost, £/MWh consumed")
ax.set_xlim(40, 85); ax.set_ylim(70, 140); ax.legend(fontsize=6.3, loc="upper left")
save(fig, "Figure_2_cost_of_self_supply")

# Fig 3 - lowest-wind fortnight of 2021: (a) normal operation, (b) total grid loss
wind, _, _ = pw.wind_fleet(P.POWER["wind_cf_central"]); pv = pw.pv_fleet()
yi = P.WEATHER_YEARS.index(2021); W, S, E = SD["wind_mw"], SD["solar_mwp"], SD["battery_mwh"]; load = d["load_mw"]
g_ = W * wind[yi] + S * pv[yi]; s0 = int(np.argmax(np.convolve(np.maximum(load - g_, 0), np.ones(336), "valid"))); sl = slice(s0, s0 + 336)
B = P.BACKUP; eta = np.sqrt(P.POWER["battery_rt"]); Lpm = 3600 / (B["efficiency"] * B["hvo_lhv_mj_l"])
def sim(outage, ren=True):
    soc = 0.5 * E; tank = B["tank_days"] * 24 * B["mw"] * Lpm; cap = tank; rec = {k: [] for k in ("ren", "dis", "grid", "block", "exp", "tank")}
    for h in range(s0, s0 + 336):
        gen = g_[h] if ren else 0.0
        net = gen - load
        if net >= 0:
            c = min(net, E / 4, (E - soc) / eta); soc += c * eta; rec["ren"].append(load); rec["dis"].append(0); rec["grid"].append(0); rec["block"].append(0); rec["exp"].append(net - c)
        else:
            dd = min(-net, E / 4, soc * eta); soc -= dd / eta; need = -net - dd
            rec["ren"].append(gen); rec["dis"].append(dd); rec["exp"].append(0)
            if outage:
                rec["grid"].append(0); rec["block"].append(need); tank = max(tank - need * Lpm, 0)
            else:
                rec["grid"].append(need); rec["block"].append(0)
        rec["tank"].append(tank / cap)
    return {k: np.array(v) for k, v in rec.items()}
fig, axs = plt.subplots(2, 1, figsize=(7.0, 4.6), sharex=True)
h = np.arange(336)
for ax, outage, ttl in ((axs[0], False, "(a) Normal operation"), (axs[1], True, "(b) Complete grid loss: islanded nodes on battery and block")):
    R = sim(outage, ren=not outage)
    ax.stackplot(h, R["ren"], R["dis"], R["grid"], R["block"], colors=[C1, C7, C2, C8],
                 labels=["Wind and solar used", "Battery", "Grid import", "Renewable-fuel block"], linewidth=0)
    ax.axhline(load, color=INK, lw=1.0, ls="--"); ax.set_ylabel("MW"); ax.set_ylim(0, load * 1.3)
    ax.set_title(ttl, loc="left", fontsize=8.5)
    if outage:
        R2 = sim(True, ren=True)
        ax2 = ax.twinx(); ax2.plot(h, 100 * R["tank"], color=INK2, lw=1.3, label="Tank, islanded nodes")
        ax2.plot(h, 100 * R2["tank"], color=INK2, lw=1.0, ls="--", label="Tank, if contracted renewables were islanded too")
        ax2.set_ylabel("HVO tank, %", color=INK2); ax2.set_ylim(0, 105)
        ax2.axhline(33, color=INK2, lw=0.8, ls=":"); ax2.grid(False); ax2.spines["right"].set_visible(True); ax2.legend(fontsize=6.3, loc="lower left")
axs[0].legend(ncol=4, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 1.32))
axs[1].set_xticks(range(0, 337, 48)); axs[1].set_xticklabels([f"day {s0 // 24 + 1 + k // 24}" for k in range(0, 337, 48)])
save(fig, "Figure_3_low_wind_fortnight")

# Fig 4 - wind-yield sensitivity of self-supply
fig, ax = plt.subplots(figsize=(5.0, 2.8))
keys = [("raw", "raw ERA5"), ("0.253", "25.3%"), ("0.3", "30%"), ("0.36", "36%")]
x = [d["wind_tests"][k]["fleet_cf"] * 100 for k, _ in keys]
ax.plot(x, [d["wind_tests"][k]["mean"] * 100 for k, _ in keys], color=C1, marker="o", label="16-year mean")
ax.plot(x, [d["wind_tests"][k]["min"] * 100 for k, _ in keys], color=C3, marker="s", label="Worst year")
ax.set_xlabel("Wind fleet capacity factor, %"); ax.set_ylabel("Hourly self-supply, %"); ax.legend(fontsize=7)
save(fig, "Figure_4_wind_yield")

# Fig 5 - heat fate by node
nodes = hc["heat"]["nodes"]
parts = [("homes_gwh", "Homes (heat, hot water, washing)", C1), ("greenhouse_gwh", "Greenhouses", C6), ("ras_gwh", "Fish and prawns", C3),
         ("seaweed_gwh", "Red-seaweed tanks", C5), ("digester_gwh", "Digesters", C7), ("drying_gwh", "Drying", C4),
         ("river_gwh", "Rejected to river", "#9fb6c9"), ("dry_cooler_gwh", "Rejected by dry coolers", "#c9c8c3")]
fig, ax = plt.subplots(figsize=(6.8, 3.1)); left = np.zeros(len(nodes)); yl = [n["node"] for n in nodes]
tot = np.array([sum(max(n[k], 0) for k, _, _ in parts) for n in nodes])
for k, lab, col in parts:
    v = 100 * np.array([max(n[k], 0) for n in nodes]) / tot; ax.barh(yl, v, left=left, color=col, label=lab, edgecolor="white", linewidth=0.6); left += v
for i, t in enumerate(tot):
    ax.text(101, i, f"{t:.0f} GWh", va="center", fontsize=6.8, color=INK2)
ax.set_xlim(0, 112); ax.set_xlabel("Share of recoverable heat at each node, %")
ax.legend(fontsize=6.3, ncol=4, loc="upper center", bbox_to_anchor=(0.45, 1.22)); ax.invert_yaxis()
save(fig, "Figure_5_heat_by_node")

# Fig 6 - monthly heat use
m = np.array(hc["heat"]["monthly_gwh"])
fig, ax = plt.subplots(figsize=(6.0, 2.8)); mo = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
ax.bar(mo, m[:, 0], color=C1, label="Homes, greenhouses, aquaculture, seaweed, digesters", edgecolor="white", linewidth=0.6)
ax.bar(mo, m[:, 1], bottom=m[:, 0], color=C4, label="Drying", edgecolor="white", linewidth=0.6)
ax.bar(mo, m[:, 2], bottom=m[:, 0] + m[:, 1], color="#c9c8c3", label="Rejected", edgecolor="white", linewidth=0.6)
ax.set_ylabel("GWh per month"); ax.legend(fontsize=6.3, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.15))
save(fig, "Figure_6_monthly_heat")

# Fig 7 - community reductions
rows = hc["ledger_full"]["rows"]; lim = hc["ledger_limited"]["rows"]
short = {"Home heating and hot water through district loops and home heat pumps": "Home heating and hot water",
         "Hot-fill washing and cleaning water": "Washing and cleaning water", "Drying contracts (fossil-fired drying displaced)": "Drying contracts",
         "Free red seaweed (Asparagopsis) for dairy and beef cattle": "Free red seaweed for cattle",
         "Manure and crop residues to digesters (storage methane avoided)": "Manure to digesters", "Methane-leak detection on digesters and upgraders": "Methane-leak detection",
         "Biomethane displacing natural gas": "Biomethane", "Farm red diesel replaced by subsidised HVO (all farms)": "Farm red diesel to HVO",
         "Household vehicles replaced by battery-electric and plug-in hybrid vehicles": "Vehicle replacement",
         "Renewable fuel for residents' remaining vehicles (HVO)": "HVO for residents' fuel", "Circular aquafeed replacing imported feed": "Circular aquafeed"}
order = sorted(rows, key=lambda k: rows[k])
fig, ax = plt.subplots(figsize=(6.2, 3.3))
ax.barh([short[k] for k in order], [rows[k] / 1e3 for k in order], color=C6, label="Full deployment", height=0.6)
ax.barh([short[k] for k in order], [lim[k] / 1e3 for k in order], color="none", edgecolor=INK2, height=0.6, label="Limited adoption, no seaweed approval")
ax.set_xlabel("kt CO$_2$e per year"); ax.legend(fontsize=6.5, loc="lower right")
save(fig, "Figure_7_community_reductions")

# Fig 8 - GPU NPV
s = de["economics"]["sensitivity_musd"]
cases = ["Central", "GPU capital +38%", "Sold 70%", "Sold 60%", "Prices -20%", "All four adverse"]
fig, ax = plt.subplots(figsize=(6.4, 3.0)); x = np.arange(len(cases)); w = 0.2
for j, (tier, path, col) in enumerate((("reservation", "prices held each generation", C1), ("reservation", "prices compress 15% per generation", "#9fc3ee"),
                                       ("on-demand", "prices held each generation", C2), ("on-demand", "prices compress 15% per generation", "#f4b399"))):
    ax.bar(x + (j - 1.5) * w, [s[f"{c}|{tier}|{path}"] / 1e3 for c in cases], width=w, color=col,
           label=f"{'US$5.87' if tier == 'reservation' else 'US$8.98'} start, {'held' if 'held' in path else 'compressing'}")
ax.axhline(0, color=INK2, lw=0.8); ax.set_xticks(x); ax.set_xticklabels(cases, fontsize=7)
ax.set_ylabel("25-year NPV, US$ bn (9%)"); ax.legend(fontsize=6.5, ncol=2, loc="lower left")
save(fig, "Figure_8_gpu_npv")
print("figures written to", FIG)
