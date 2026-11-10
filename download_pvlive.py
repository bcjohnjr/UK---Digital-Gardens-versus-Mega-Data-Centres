#!/usr/bin/env python3
"""Fetch Sheffield Solar regional PV_Live estimates (NOT site-metered PV).
Read: https://www.solar.sheffield.ac.uk/api/
Python download_pvlive.py --pes-id 10 --start 2020-01-01 --end 2021-01-01
Check actual PES ID from https://api.pvlive.uk/pvlive/api/v4/pes_list
"""
import argparse,urllib.request,json,csv
from urllib.parse import urlencode
from pathlib import Path

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Digital-Gardens-EES-independent-validation/1.0'})
    with urllib.request.urlopen(req,timeout=60) as r:return r.read()
def main():
    a=argparse.ArgumentParser();a.add_argument('--pes-id',type=int,required=True)
    a.add_argument('--start',required=True);a.add_argument('--end',required=True)
    a.add_argument('--output',default='PVLIVE_PES.csv');args=a.parse_args()
    root='https://api.pvlive.uk/pvlive/api/v4/'
    try:
        pes=json.loads(fetch(root+'pes_list'));print('Available PES metadata:',str(pes)[:1600]);
    except Exception as e:print('PES metadata check failed:',e)
    url=f'{root}pes/{args.pes_id}?'+urlencode({'start':args.start+'T00:00:00','end':args.end+'T00:00:00','data_format':'csv'})
    content=fetch(url);Path(args.output).write_bytes(content)
    print('Saved',args.output,'bytes',len(content),'source',url)
    print('Regional PV outturn is not site-level turbine/panel validation.')
if __name__=='__main__':main()
