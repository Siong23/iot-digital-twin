#!/usr/bin/env python3
"""
01_build_master_flow_table_minimal.py
Create flows_master.parquet from dataset/processed_dataset/flows/*.csv
Writes into dataset/processed_dataset/processed_for_model/flows_master.parquet
"""
import json, os
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("dataset/processed_dataset")
FLOWS_DIR = ROOT / "flows"
OUT_DIR = ROOT / "processed_for_model"
OUT_DIR.mkdir(parents=True, exist_ok=True)

KEEP_COLS = [
  'uid','ts','id.orig_h','id.resp_h','id.orig_p','id.resp_p','proto','service',
  'duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes','conn_state',
  'dns_q_count','http_count','tls_count','files_count','mqtt_pub_count','notice_count',
  'pcap_id','class','device'
]

def safe_read_csv(p):
    try:
        return pd.read_csv(p, low_memory=False)
    except Exception as e:
        print("Failed reading", p, ":", e)
        return pd.DataFrame()

def cast_numeric(df):
    for c in ['ts','duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes',
              'dns_q_count','http_count','tls_count','files_count','mqtt_pub_count','notice_count']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        else:
            df[c] = np.nan
    return df

def main():
    all_paths = sorted(FLOWS_DIR.glob("*.csv"))
    print("Found flow CSVs:", len(all_paths))
    list_df = []
    for p in all_paths:
        df = safe_read_csv(p)
        if df.empty: continue
        if 'pcap_id' not in df.columns:
            df['pcap_id'] = p.stem
        df = cast_numeric(df)
        for c in KEEP_COLS:
            if c not in df.columns:
                df[c] = np.nan
        df = df[KEEP_COLS]
        list_df.append(df)
    if not list_df:
        print("No flows found, exiting.")
        return
    master = pd.concat(list_df, ignore_index=True, sort=False)
    master['orig_bytes'] = master['orig_bytes'].fillna(0)
    master['resp_bytes'] = master['resp_bytes'].fillna(0)
    master['orig_pkts'] = master['orig_pkts'].fillna(0)
    master['resp_pkts'] = master['resp_pkts'].fillna(0)
    master['bytes_total'] = master['orig_bytes'] + master['resp_bytes']
    master['pkts_total'] = master['orig_pkts'] + master['resp_pkts']
    master['bytes_per_pkt'] = master.apply(lambda r: (r['bytes_total']/r['pkts_total']) if r['pkts_total']>0 else 0, axis=1)
    master['ts'] = pd.to_numeric(master['ts'], errors='coerce').fillna(0.0)
    # flow_size_bucket as simple labels (not saving category maps)
    master['flow_size_bucket'] = pd.cut(master['bytes_total'].fillna(0),
                                       bins=[-1,100,1000,10000,100000,1e12],
                                       labels=['tiny','small','medium','large','huge'])
    out_path = OUT_DIR / "flows_master.parquet"
    master.to_parquet(out_path, index=False)
    print("Wrote master flows parquet:", out_path)

if __name__ == "__main__":
    main()
