#!/usr/bin/env python3
"""Four-hour, power-limited battery screen after loss of one 55 MW unit.

Screening-only: assumes a full battery at the event, instantaneous 55 MW surviving GT supply,
constant 101.326 MW node demand and 0.5 MW modelled network losses. Does not establish
frequency/inertia, black start, dynamic stability, dispatch priority or protection adequacy.
"""
import csv, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import params as P

def main():
    o=P.OUT;d=json.load(open(o/'island_network.json')); t=d['gt_n1']
    total=d['total_load_mw']+d['losses_mw']; gen=t['remaining_mw']
    if not (abs(total-gen-t['shortfall_mw']) < 1e-8):raise AssertionError('power does not balance')
    ts=np.arange(0,8.01,.25)
    b=np.where(ts<4,t['battery_delivered_mw'],0.0)
    missing=np.maximum(total-gen-b,0.0)
    with open(o/'TURBINE_N1_POWER_LIMIT.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(['hour_since_unit_trip','surviving_gt_mw','battery_mw','unserved_mw','load_plus_losses_mw']);
        for x,y,z in zip(ts,b,missing):w.writerow([f'{x:.2f}',f'{gen:.4f}',f'{y:.4f}',f'{z:.4f}',f'{total:.4f}'])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(6.7,3.65))
    ax.fill_between(ts,0,gen,color='#315f85',alpha=.85,label='Surviving generator (55 MW)',step='post')
    ax.fill_between(ts,gen,gen+b,color='#6da779',alpha=.9,label='Battery (25 MW for 4 h)',step='post')
    ax.fill_between(ts,gen+b,total,color='#d69b80',alpha=.86,label='Unserved load / losses',step='post')
    ax.axhline(total,color='#2c2c2c',lw=1.15,ls='--')
    ax.axvline(4,color='#424242',lw=.8,ls=':')
    ax.text(0.14,86.2,'21.8 MW shed immediately',color='#52261d',fontsize=8.4)
    ax.text(4.18,85.4,'46.8 MW shed after 4 h',color='#52261d',fontsize=8.4)
    ax.text(4.04,4,'Battery empty at 4 h',color='#303030',fontsize=7.8,rotation=90)
    ax.set_xlim(0,8);ax.set_ylim(0,114)
    ax.set_xlabel('Elapsed hours since loss of one 55 MW unit')
    ax.set_ylabel('Power (MW)')
    ax.set_title('Loss of one standby unit: power-limited battery response',fontsize=10)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,1.01),fontsize=7,ncol=3,frameon=False)
    ax.grid(axis='y',alpha=.18)
    fig.tight_layout()
    out=P.HERE.parent/'FIGURES';out.mkdir(parents=True,exist_ok=True)
    fig.savefig(out/'Figure_9_turbine_trip.png',dpi=300,bbox_inches='tight')
    fig.savefig(out/'Figure_9_turbine_trip.pdf',bbox_inches='tight')
    plt.close(fig)
    print('Turbine-trip screen: initial unserved %.3f MW, battery %.3f MW x %.1f h, after %.3f MW' %
          (t['immediate_unserved_mw'],t['battery_delivered_mw'],t['battery_duration_at_rated_power_h'],t['unserved_after_battery_mw']))
if __name__=='__main__':main()
