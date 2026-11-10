#!/usr/bin/env python3
"""Transparent sensitivity addendum for EES version 2: not additional measurements.
Run after design_trajectory.py, heat_community.py, design_econ.py.
"""
import json,math,csv
import params as P
O=P.OUT
j=lambda x:json.load(open(O/x))
d=j('design.json'); hc=j('heat_community.json'); de=j('design_econ.json');dt=j('design_trajectory.json')
L_gwh=d['annual_load_gwh']; s=d['selected']; ref=hc['ledger_full']['total_t']; horizon=25
result={
 'basis':'model assumptions, no independently metered host-community outcomes',
 'wind_model':{'curve':'piecewise generic 4-5 MW onshore curve; 12% losses; not manufacturer-certified',
               'raw_era5_100m_cf':d['wind_tests']['raw']['fleet_cf'],
               'calibrated_30pct_cf':d['wind_tests']['0.3']['fleet_cf'],
               'selected_portfolio':{k:s[k] for k in ('wind_mw','solar_mwp','battery_mwh','self_supply','cost_full','import_gwh','export_gwh')}},
 'non_commodity_tariff':{'original_flat_tnuos_proxy_gbp_mwh':P.COSTS['non_commodity_gbp_mwh']['tnuos'],
                         'base_all_other_charges_gbp_mwh':sum(P.COSTS['non_commodity_gbp_mwh'].values())-P.COSTS['non_commodity_gbp_mwh']['tnuos'],
                         'note':'Original flat proxy is NOT a validated actual 2026/27 TNUoS tariff. Demand residual charges can be daily fixed site/band levies and other locational terms.'},
 'community_avoided_emissions_25y':{},
 'vehicles_embodied':{},
 'backup_startup':{'battery_mwh':s['battery_mwh'],'battery_power_mw':s['battery_mwh']/P.POWER['battery_hours'],
                   'battery_initial_soc_mwh':s['battery_mwh']/2,'load_mw':d['load_mw'],
                   'one_gt_remaining_mw':P.ISLAND['gt_unit_mw'],
                   'instantaneous_gap_after_one_gt_mw':max(0,d['load_mw']-P.ISLAND['gt_unit_mw']),
                   'note':'The power-limited battery alone cannot bridge the full outage load; black start and fast-response capacity not established.'}
}
for decline in (0,.02,.05,.1):
    avoided_t=sum(ref*(1-decline)**year for year in range(horizon))
    result['community_avoided_emissions_25y'][f'{decline:.0%}_annual_decline']={
        'gross_conditional_avoided_kt':avoided_t/1000,
        'gross_original_constant_baseline_kt':ref*horizon/1000,
        'lifecycle_dg_net_kt':dt['cum']['dg_lca_kt']-avoided_t/1000,
        'note':'Counterfactual decline applies to all categories as stylised sensitivity; not a sector-specific forecast'}
for per_vehicle in (8,10,12):
    vehicles=hc['programme']['vehicles']['total']
    result['vehicles_embodied'][str(per_vehicle)+'_t_co2e_per_new_vehicle']={
       'vehicles':vehicles,'gross_t_co2e':vehicles*per_vehicle,
       'annualised_gross_t_per_year_at_12y':vehicles*per_vehicle/12,
       'note':'Conservative gross manufacturing footprint; not an incremental EV-versus-ICE manufacturing difference'}
for annual_fixed in (0,5e6,15e6,30e6):
    eff=annual_fixed/(L_gwh*1e3)
    key=f'{annual_fixed/1e6:.0f}_million_gbp_per_year'
    result['non_commodity_tariff'][key]={'new_fixed_equiv_gbp_mwh':eff,
        'dg_delivered_gbp_mwh_if_proxy_replaced':de['economics']['dg_delivered']-P.COSTS['non_commodity_gbp_mwh']['tnuos']+eff,
        'note':'Illustrative sum over project sites; not based on awarded utility tariffs'}
(O/'REVISED_SENSITIVITY.json').write_text(json.dumps(result,indent=2))
with open(O/'REVISED_SENSITIVITY.csv','w',newline='') as f:
 w=csv.writer(f);w.writerow(['category','scenario','metric','value'])
 for k,cat in result.items():
  if isinstance(cat,dict):
   for scen,v in cat.items():
    if isinstance(v,dict):
     for kk,val in v.items():
      if isinstance(val,(int,float)):w.writerow([k,scen,kk,val])
print(json.dumps(result,indent=2)[:4500])
