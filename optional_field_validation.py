#!/usr/bin/env python3
"""OPTIONAL independent production validation for the North Tyne study.

Inputs are NOT shipped in the research package. Ofgem REGO output requires the
user to export a station's actual records; PV_Live uses regional estimates, not
metered output from the proposed Digital Gardens PV plants.

Example (Ray REGO monthly output exported by user):
 python optional_field_validation.py --rego Ray_REGO.csv --date-col month --mwh-col generation_mwh --capacity-mw 54.4

CSV date formats: 2020-03, 2020-03-01, 01/03/2020, or full ISO datetimes.
"""
import argparse, csv, json
import numpy as np
import pandas as pd
from pathlib import Path
from data_io import load_site
from power_247 import power_curve
import params as P


def run_rego(filename, date_col, mwh_col, capacity, wind_site, height=73, ref_height=100, alpha=.14):
    df=pd.read_csv(filename)
    for c in (date_col,mwh_col):
        if c not in df:raise SystemExit(f'Missing required column {c!r}. Available: {list(df.columns)}')
    dt=pd.to_datetime(df[date_col], errors='coerce', dayfirst=False)
    if dt.isna().all():dt=pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
    df['month']=dt.dt.to_period('M').astype(str)
    df['actual_mwh']=pd.to_numeric(df[mwh_col].astype(str).str.replace(',',''), errors='coerce')
    df=df.dropna(subset=['actual_mwh'])
    # Filter to study interval and do not silently mix duplicate/revoked entries.
    df=df[(df['month']>='2010-01')&(df['month']<='2025-12')].groupby('month',as_index=False)['actual_mwh'].sum()
    if df.empty: raise SystemExit('No valid REGO monthly observations for 2010–2025')
    data=load_site(wind_site,cols=('wind_speed_100m',))['wind_speed_100m']
    factor=(height/ref_height)**alpha
    rows=[]
    for yi,year in enumerate(P.WEATHER_YEARS):
        idx=pd.date_range(f'{year}-01-01',f'{year}-12-31 23:00',freq='h',tz='UTC')
        idx=idx[~((idx.month==2)&(idx.day==29))]
        assert len(idx)==8760
        out=power_curve(data[yi]*factor)
        for mon in range(1,13):
            ix=(idx.month==mon); mwh=float(capacity*out[ix].sum()); hrs=int(ix.sum())
            rows.append(dict(month=f'{year}-{mon:02d}',model_mwh=mwh,model_cf=float(out[ix].mean()),hours=hrs))
    model=pd.DataFrame(rows)
    pair=model.merge(df,on='month',how='inner').sort_values('month')
    pair['observed_cf']=pair['actual_mwh']/(capacity*pair['hours'])
    if len(pair)<3: print('Caution: fewer than 3 matched months')
    pair.to_csv('WIND_MEASURED_VS_MODELLED.csv',index=False)
    corr=float(pair[['model_cf','observed_cf']].corr().iloc[0,1]) if len(pair)>1 else None
    stats=dict(n_months=len(pair),capacity_mw=capacity,hub_m=height,era5_reference_m=ref_height,alpha=alpha,
               raw_model_annual_cf=float(model.model_mwh.sum()/(capacity*model.hours.sum())),
               matched_model_cf=float(pair.model_mwh.sum()/(capacity*pair.hours.sum())),
               matched_observed_cf=float(pair.actual_mwh.sum()/(capacity*pair.hours.sum())),
               pearson_r=corr,rmse_cf=float(np.sqrt(np.mean((pair.model_cf-pair.observed_cf)**2))),
               status='Measured-farm comparison only; different turbine and exact locations prevent full validation')
    return stats


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument('--rego',help='Ofgem REGO CSV exported for Ray or Middlemoor (not downloaded automatically)')
    ap.add_argument('--date-col',default='month');ap.add_argument('--mwh-col',default='generation_mwh')
    ap.add_argument('--capacity-mw',type=float,default=54.4);ap.add_argument('--hub-m',type=float,default=73)
    ap.add_argument('--wind-site',default='ridsdale_ray_wind_proxy')
    args=ap.parse_args()
    if not args.rego: ap.print_help();return
    stats=run_rego(args.rego,args.date_col,args.mwh_col,args.capacity_mw,args.wind_site,args.hub_m)
    Path('FIELD_VALIDATION.json').write_text(json.dumps(stats,indent=2))
    print(json.dumps(stats,indent=2))
if __name__=='__main__':main()
