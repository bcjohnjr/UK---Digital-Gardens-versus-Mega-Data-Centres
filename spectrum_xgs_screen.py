#!/usr/bin/env python3
"""Physical lower-bound North Tyne fibre screen, NOT measured XGS performance.
Scale-across hardware and NCCL results: NVIDIA vendor technical note (2025).
This computation uses payload bits/(physical link rate * duty factor) and
fibre propagation at 5 microseconds per km in one direction. No protocol,
collective-tree or congestion overhead is included; actual time >= this bound.
"""
import json,csv
from pathlib import Path
import params as P
out=[]
for distance_km in (10,30,60):
    one_way_ms=distance_km*0.005
    for link_gbps in (400,800):
        for data_gb in (100,1000,100000):
            transfer_sec=data_gb*8/(link_gbps*.70) # decimal GB / Gbps
            out.append({'distance_km':distance_km,'link_gbps':link_gbps,'payload_GB_decimal':data_gb,
                        'assumed_payload_efficiency':.70,'min_transfer_seconds':transfer_sec,
                        'propagation_one_way_ms':one_way_ms,'propagation_rtt_ms':2*one_way_ms,
                        'site_to_site_actual_NCCL_allreduce':'unmeasured',
                        'interpretation':'Ideal transfer lower bound, not full synchronized-training performance'})
path=P.OUT/'SPECTRUM_XGS_LOWER_BOUNDS.csv';path.parent.mkdir(parents=True,exist_ok=True)
with open(path,'w',newline='') as f:
 w=csv.DictWriter(f,out[0].keys());w.writeheader();w.writerows(out)
(P.OUT/'SPECTRUM_XGS_LOWER_BOUNDS.json').write_text(json.dumps(out,indent=2))
print('Wrote',path,len(out),'screen rows')
if __name__=='__main__':pass
