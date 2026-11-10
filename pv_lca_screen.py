#!/usr/bin/env python3
"""One-at-a-time solar PV lifecycle factor screen, holding hourly dispatch and procurement fixed.

Original study uses 35 gCO2e/kWh as an illustrative assumption, rather than an IPCC median.
The 48 g sensitivity is the IPCC AR5 WGIII Annex III utility-PV median.
"""
import json, csv
import numpy as np
import params as P
import power_247 as pw
from data_io import load_grid

def main():
    d=json.load(open(P.OUT/'design.json')); s=d['selected']; load=d['load_mw']
    grid=load_grid();m25=float(np.nanmean(grid['price'][-1]));grid['price_norm']=grid['price']/np.nanmean(grid['price'],axis=1,keepdims=True)*m25
    for key in ('price','price_norm','gb_intensity','ne_intensity'):
        grid[key]=np.nan_to_num(grid[key],nan=float(np.nanmean(grid[key])))
    wind,_,_=pw.wind_fleet(P.POWER['wind_cf_central']);pv=pw.pv_fleet()
    gy=[P.WEATHER_YEARS.index(y) for y in P.GRID_YEARS]
    W,S,E=np.array([s['wind_mw']]),np.array([s['solar_mwp']]),np.array([s['battery_mwh']]);Pw=E/P.POWER['battery_hours'];A=np.zeros(1)
    out=[]
    initial=P.LCA['solar_g_kwh']
    for factor in (35.0,48.0):
        P.LCA['solar_g_kwh']=factor
        r=pw.evaluate(W,S,E,Pw,A,wind,pv,grid,load,gy,pw.biogas_mwh_per_year())
        vals=r['lca_t'][0]
        out.append(dict(solar_lca_gco2e_kwh=factor, annual_lca_generation_allocated_t=float(vals.mean()),
                        annual_lca_total_with_scheduled_backup_t=float(vals.mean() + (s['lca_t']-out[0]['annual_lca_generation_allocated_t'] if out else 0)),
                        delta_from_35_t=float(vals.mean()-out[0]['annual_lca_generation_allocated_t'] if out else 0),
                        count_years=len(vals)))
    P.LCA['solar_g_kwh']=initial
    # Preserve the original absolute baseline, which includes scheduled backup test emissions.
    original=s['lca_t'];out[0]['annual_lca_total_with_scheduled_backup_t']=original
    out[1]['annual_lca_total_with_scheduled_backup_t']=original+out[1]['delta_from_35_t']
    json.dump({'screen':'fixed model output, change solar PV LCA intensity only', 'cases':out,
               'baseline_partial_lifecycle_kt_yr':json.load(open(P.OUT/'design_econ.json'))['net']['dg_lca_kt_yr'],
               'sensitivity_partial_lifecycle_kt_yr':json.load(open(P.OUT/'design_econ.json'))['net']['dg_lca_kt_yr']+out[1]['delta_from_35_t']/1000,
               'estimated_25year_increment_kt':out[1]['delta_from_35_t']*25/1000},open(P.OUT/'PV_LCA_SCREEN.json','w'),indent=2)
    with open(P.OUT/'PV_LCA_SCREEN.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
