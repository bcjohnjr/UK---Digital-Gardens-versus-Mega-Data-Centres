#!/usr/bin/env python3
"""Islanded 33 kV network from the Hexham block to the eight nodes: steady-state load flow (radial, approximate AC voltage drop),
thermal loading, losses, N-1 circuit contingencies, loss of one gas-turbine unit, and cost. Screening study, not a protection
or dynamic-stability study."""
import json, math
import numpy as np
import params as P

IS = P.ISLAND


def node_loads_mw():
    d = json.load(open(P.OUT / "design.json"))
    comm = d["community_mw"]; it = P.NETWORK["it_mw"]
    nodes = {r["node"]: r for r in json.load(open(P.OUT / "heat_community.json"))["heat"]["nodes"]} if (P.OUT / "heat_community.json").exists() else None
    from data_io import load_communities
    c = load_communities()
    loads = {}
    pop_tot = sum(c[n]["population"] for n in P.NODES)
    for n in P.NODES:
        it_mw = c[n]["it_mw"]
        loads[n] = it_mw * P.NETWORK["it_utilisation"] * P.NETWORK["pue"] + comm * c[n]["population"] / pop_tot
    return loads, d["load_mw"]


def flows(loads, routes, circuits):
    """Radial flows from Hexham. Returns per-route MW, per-circuit amps, voltage at each node (p.u.) and losses (MW)."""
    child = {}
    for a, b, km in routes:
        child.setdefault(a, []).append((b, km))
    def downstream(n):
        return loads[n] + sum(downstream(c) for c, _ in child.get(n, []))
    res = {}; v = {"hexham": 1.0}; loss = 0.0
    def walk(n):
        nonlocal loss
        for c, km in child.get(n, []):
            p = downstream(c); s = p / IS["pf"]; q = s * math.sqrt(1 - IS["pf"] ** 2)
            ncirc = circuits.get((n, c), IS["circuits"])
            i_tot = s * 1e6 / (math.sqrt(3) * IS["kv"] * 1e3 * v[n]); i_c = i_tot / ncirc
            r = IS["r_ohm_km"] * km / ncirc; x = IS["x_ohm_km"] * km / ncirc
            dv = (r * p + x * q) / (IS["kv"] ** 2 * v[n])                     # p.u. drop
            v[c] = v[n] - dv
            l = 3 * i_tot ** 2 * r / 1e6; loss += l
            res[f"{P.NODE_LABEL[n]}–{P.NODE_LABEL[c]}"] = dict(km=km, mw=p, amps_per_circuit=i_c, loading=i_c / IS["ampacity_a"], drop_pu=dv, loss_mw=l)
            walk(c)
    walk("hexham")
    return res, v, loss


def main():
    loads, total = node_loads_mw()
    routes = IS["routes"]
    base, vb, lb = flows(loads, routes, {})
    cont = {}
    for a, b, km in routes:
        r, v, l = flows(loads, routes, {(a, b): IS["circuits"] - 1})
        cont[f"{P.NODE_LABEL[a]}–{P.NODE_LABEL[b]} one circuit out"] = dict(max_loading=max(x["loading"] for x in r.values()),
                                                                             min_v=min(v.values()), loss_mw=l)
    worst = max(cont.values(), key=lambda x: x["max_loading"])
    route_km = sum(km for _, _, km in routes); circuit_km = route_km * IS["circuits"]
    capex = circuit_km * P.BACKUP["island_network_gbp_km"] + P.BACKUP["island_switchgear_gbp"]
    gen_n1 = (IS["gt_units"] - 1) * IS["gt_unit_mw"]
    d = json.load(open(P.OUT / "design.json")); E = d["selected"]["battery_mwh"]
    # Four-hour battery POWER rating is binding in an N-1 generator event.
    # E/short is an energy-only upper bound, not dispatchable ride-through time.
    short = max(total + lb - gen_n1, 0.0)
    battery_power_mw = E / P.POWER["battery_hours"]
    battery_delivery_mw = min(short, battery_power_mw)
    immediate_unserved_mw = max(short - battery_delivery_mw, 0.0)
    rated_duration_h = (E / battery_delivery_mw) if battery_delivery_mw > 0 else 0.0
    after_battery_unserved_mw = short
    out = dict(node_load_mw={P.NODE_LABEL[n]: v for n, v in loads.items()}, total_load_mw=total, routes=base,
               voltage_pu={P.NODE_LABEL[n]: x for n, x in vb.items()}, min_voltage_pu=min(vb.values()), losses_mw=lb,
               max_loading=max(x["loading"] for x in base.values()), n1=cont, n1_worst_loading=worst["max_loading"],
               n1_min_voltage_pu=min(x["min_v"] for x in cont.values()), route_km=route_km, circuit_km=circuit_km, capex_gbp=capex,
               gt_n1=dict(remaining_mw=gen_n1, shortfall_mw=short,
                          battery_energy_mwh=E, battery_power_mw=battery_power_mw,
                          battery_delivered_mw=battery_delivery_mw,
                          immediate_unserved_mw=immediate_unserved_mw,
                          battery_duration_at_rated_power_h=rated_duration_h,
                          unserved_after_battery_mw=after_battery_unserved_mw,
                          immediate_load_shed_fraction=immediate_unserved_mw / total,
                          post_battery_load_shed_fraction=after_battery_unserved_mw / total,
                          # Energy-only value retained for comparison and labelled infeasible as uninterrupted cover:
                          energy_only_hours_if_unlimited_power=E / short if short > 0 else None,
                          it_curtailment_share=short / (P.NETWORK["it_mw"] * P.NETWORK["it_utilisation"] * P.NETWORK["pue"])),
               limits=dict(v_limit=IS["v_limit"], ampacity_a=IS["ampacity_a"]))
    json.dump(out, open(P.OUT / "island_network.json", "w"), indent=2, default=float)
    print(json.dumps({k: v for k, v in out.items() if k not in ("routes", "n1")}, indent=1, default=float))
    for k, v in base.items():
        print(f"  {k:28s} {v['km']:5.1f} km {v['mw']:6.1f} MW {v['amps_per_circuit']:6.0f} A/circuit {100*v['loading']:5.1f}% drop {100*v['drop_pu']:.2f}%")


if __name__ == "__main__":
    main()
