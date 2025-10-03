#!/usr/bin/env python3
"""
packet_aggregator_from_pcaps.py

Requirements:
 - tshark must be installed and in PATH.
 - The script expects PCAP files to be in a parallel directory structure next to Zeek logs
   or you can set PCAP_BASE to point to your PCAP root.

What it does:
 - For each per-pcap flows CSV produced by the previous script, finds corresponding PCAP
   and runs tshark to extract packets with fields: frame.time_epoch, ip.src, ip.dst, tcp.srcport, tcp.dstport, frame.len, tcp.analysis.retransmission
 - Aggregates packet-level stats per flow (matching uses 5-tuple + approximate timestamp window)
 - Produces per-flow packet aggregates CSV and merges into a combined merged CSV.

Note: packet->flow matching can be imperfect if flows cross NAT or use different tuple mappings.
Use as a practical, best-effort aggregator for packet-level features.
"""
import os, glob, subprocess, csv, json, math
from pathlib import Path
import pandas as pd
import numpy as np
import shlex

# === CONFIG ===
PCAP_BASE = "/mnt/data/PCAPs"            # point to your PCAP folder root (adjust)
FLOWS_DIR = "/mnt/data/csv_output"       # where flows_<pcap_id>.csv are located
OUT_DIR = "/mnt/data/csv_output/packet_aggregates"
TSHARK_CMD = "tshark"                    # ensure tshark is available

os.makedirs(OUT_DIR, exist_ok=True)

# helper to find pcap file corresponding to pcap_id (best-effort)
def find_pcap_for_pcapid(pcap_id, base=PCAP_BASE):
    # try to find a file whose path contains the parts of pcap_id
    tokens = pcap_id.split("_")
    matches = []
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.lower().endswith(".pcap") or f.lower().endswith(".pcapng"):
                p = os.path.join(root,f)
                if all(tok in p for tok in tokens if tok and not tok.isdigit()):
                    matches.append(p)
    if matches:
        return matches[0]
    # fallback: try any pcap in base
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.lower().endswith(".pcap") or f.lower().endswith(".pcapng"):
                return os.path.join(root,f)
    return None

# gather all per-pcap flows csvs
flow_files = glob.glob(os.path.join(FLOWS_DIR, "**", "flows_*.csv"), recursive=True)
print("Found", len(flow_files), "flows CSV files.")

for flow_csv in flow_files:
    try:
        df = pd.read_csv(flow_csv, dtype=str)
    except Exception as e:
        print("Could not read", flow_csv, e)
        continue
    if df.empty:
        continue
    # pcap_id is in filename or column
    pcap_id = None
    if "pcap_id" in df.columns:
        pcap_id = df["pcap_id"].iloc[0]
    else:
        # parse from filename
        fname = Path(flow_csv).stem
        # flows_<pcapid>
        if fname.startswith("flows_"):
            pcap_id = fname[len("flows_"):]
        else:
            pcap_id = fname
    print("Processing", pcap_id)

    # find PCAP
    pcap_path = find_pcap_for_pcapid(pcap_id, base=PCAP_BASE)
    if not pcap_path:
        print("PCAP not found for", pcap_id, "— skipping packet aggregates.")
        continue

    # Create packet CSV via tshark (fields: time_epoch, ip.src, ip.dst, tcp.srcport, tcp.dstport, udp.srcport, udp.dstport, frame.len, tcp.analysis.retransmission)
    pkt_csv = os.path.join(OUT_DIR, f"packets_{pcap_id}.csv")
    tshark_fields = [
        "-T", "fields",
        "-e", "frame.time_epoch",
        "-e", "ip.src",
        "-e", "ip.dst",
        "-e", "tcp.srcport",
        "-e", "tcp.dstport",
        "-e", "udp.srcport",
        "-e", "udp.dstport",
        "-e", "frame.len",
        "-e", "tcp.analysis.retransmission",
        "-E", "header=y",
        "-E", "separator=,",
    ]
    cmd = [TSHARK_CMD, "-r", pcap_path] + tshark_fields
    print("Running tshark for", pcap_path)
    with open(pkt_csv, "w") as outfh:
        proc = subprocess.Popen(cmd, stdout=outfh, stderr=subprocess.DEVNULL)
        proc.wait()

    # Load packets CSV (this may be large; process in chunks if needed)
    pkts_df = pd.read_csv(pkt_csv)
    # Normalize ports: prefer tcp ports then udp ports
    pkts_df["src_port"] = pkts_df["tcp.srcport"].fillna(pkts_df["udp.srcport"]).fillna("").astype(str)
    pkts_df["dst_port"] = pkts_df["tcp.dstport"].fillna(pkts_df["udp.dstport"]).fillna("").astype(str)
    pkts_df["frame.len"] = pd.to_numeric(pkts_df["frame.len"], errors="coerce").fillna(0).astype(int)
    pkts_df["frame.time_epoch"] = pd.to_numeric(pkts_df["frame.time_epoch"], errors="coerce")
    # For matching, build tuple key
    pkts_df["five_tuple"] = pkts_df[["ip.src","ip.dst","src_port","dst_port"]].astype(str).agg("|".join, axis=1)

    # build per-5tuple aggregates
    agg_funcs = {
        "frame.len":["count","min","max","mean"],
        "frame.time_epoch":["min","max"]
    }
    grouped = pkts_df.groupby("five_tuple").agg(agg_funcs)
    # flatten columns
    grouped.columns = ["_".join(col).strip() for col in grouped.columns.values]
    grouped = grouped.reset_index()
    # compute iat mean by sorting timestamps per five_tuple
    iat_rows = []
    for key, sub in pkts_df.groupby("five_tuple"):
        times = sub["frame.time_epoch"].dropna().sort_values().values
        if len(times) <= 1:
            iat_mean = 0.0
            iat_p90 = 0.0
        else:
            diffs = np.diff(times)
            iat_mean = float(np.mean(diffs))
            iat_p90 = float(np.percentile(diffs, 90))
        iat_rows.append({"five_tuple": key, "iat_mean": iat_mean, "iat_p90": iat_p90})
    iat_df = pd.DataFrame(iat_rows)
    merged = grouped.merge(iat_df, on="five_tuple", how="left")

    # Map per-flow rows by trying to match flow tuples in flows CSV
    # Build flow five_tuple in same format (src_ip|dst_ip|src_port|dst_port)
    # Use the flows DF (first read earlier)
    flows_df = df.copy()
    for col in ["src_ip","dst_ip","src_port","dst_port"]:
        if col not in flows_df.columns:
            flows_df[col] = ""
    flows_df["five_tuple"] = flows_df["src_ip"].astype(str) + "|" + flows_df["dst_ip"].astype(str) + "|" + flows_df["src_port"].astype(str) + "|" + flows_df["dst_port"].astype(str)

    # Left join merged packet stats into flows_df by five_tuple
    flows_df = flows_df.merge(merged, on="five_tuple", how="left")
    # fill NaN with zeros
    for c in ["frame.len_count","frame.len_min","frame.len_max","frame.len_mean","frame.time_epoch_min","frame.time_epoch_max","iat_mean","iat_p90"]:
        if c in flows_df.columns:
            flows_df[c] = flows_df[c].fillna(0)
    out_merged = os.path.join(OUT_DIR, f"flows_with_pktagg_{pcap_id}.csv")
    flows_df.to_csv(out_merged, index=False)
    print("Wrote per-flow packet-agg merged CSV:", out_merged)

print("Packet aggregation complete. Outputs under:", OUT_DIR)
