#!/usr/bin/env python3
"""
zeek_to_csv_minimal.py
Minimal: convert Zeek logs -> per_pcap conn.csv and a simplified per-pcap flows CSV.
Writes:
  - <out_root>/per_pcap_csvs/<class>/<seq>/<device>/conn.csv
  - <out_root>/flows/<pcap_id>.csv
"""
import os, sys, json, gc
from pathlib import Path
import pandas as pd

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--zeek-root", default="dataset/ZEEK_LOGS")
parser.add_argument("--out-root", default="dataset/processed_dataset")
args = parser.parse_args()

ZE = Path(args.zeek_root)
OUT = Path(args.out_root)
PER_PCAP = OUT / "per_pcap_csvs"
FLOWS = OUT / "flows"
PER_PCAP.mkdir(parents=True, exist_ok=True)
FLOWS.mkdir(parents=True, exist_ok=True)

def parse_zeek_log_to_df(logpath):
    cols=None; rows=[]
    try:
        with open(logpath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line=line.rstrip("\n")
                if not line: continue
                if line.startswith("#fields"):
                    parts=line.split("\t"); cols=parts[1:]; continue
                if line.startswith("#"): continue
                if cols is None: continue
                parts=line.split("\t")
                if len(parts)<len(cols): parts += [""]*(len(cols)-len(parts))
                rows.append(parts[:len(cols)])
    except Exception:
        return pd.DataFrame()
    if cols is None: return pd.DataFrame()
    try:
        df=pd.DataFrame(rows, columns=cols)
    except Exception:
        df=pd.DataFrame(rows); df.columns=cols[:df.shape[1]]
    return df

for zeek_dir in sorted(ZE.rglob("zeek_logs")):
    if not zeek_dir.is_dir(): continue
    # infer pcap_id
    parts = zeek_dir.parts
    if "zeek_logs" in parts:
        i = parts.index("zeek_logs")
        if i >= 3:
            cls, seq, device = parts[i-3], parts[i-2], parts[i-1]
        else:
            cls, seq, device = "unknown","0","unknown"
    else:
        cls, seq, device = "unknown","0","unknown"
    pcap_id = f"{cls}_{seq}_{device}"
    per_pcap_out = PER_PCAP / cls / seq / device
    per_pcap_out.mkdir(parents=True, exist_ok=True)
    # parse conn.log if present
    clp = zeek_dir / "conn.log"
    if clp.exists():
        cdf = parse_zeek_log_to_df(str(clp))
        try:
            cdf.to_csv(per_pcap_out / "conn.csv", index=False)
        except Exception:
            pass
        # build minimal flows csv with selected columns
        keep = ['uid','ts','id.orig_h','id.resp_h','id.orig_p','id.resp_p','proto','service','duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes','conn_state','history']
        for col in keep:
            if col not in cdf.columns:
                cdf[col] = ""
        flows_df = cdf[keep].copy()
        flows_df['pcap_id'] = pcap_id
        flows_df['class'] = cls
        flows_df['device'] = device
        flows_df.to_csv(FLOWS / f"{pcap_id}.csv", index=False)
    else:
        # no conn.log: still ensure directory exists so downstream skips gracefully
        open(per_pcap_out / ".no_conn", "a").close()

print("zeek_to_csv_minimal: done.")

