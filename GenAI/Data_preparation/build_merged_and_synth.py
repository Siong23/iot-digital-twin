#!/usr/bin/env python3
"""
build_merged_and_synth.py

Combined pipeline:
  1) Merge per-pcap CSV logs under: per_pcap_csvs/<CLASS>/<SEQ>/<DEVICE>/*.csv
      -> merged/<CLASS>_<SEQ>_<DEVICE>.csv (event timeline)
  2) Concatenate all merged CSVs -> all_events.csv
  3) Optionally synthesize one PCAP per merged file (simple pcapizer using scapy)

Usage:
  - Default (merge + concat):
      python3 build_merged_and_synth.py --merge --concat
  - With synthesis (requires scapy):
      python3 build_merged_and_synth.py --merge --concat --synthesize

Author: ChatGPT (defensive example)
"""

import os
import argparse
from pathlib import Path
import pandas as pd
import random
import math
import json
import sys

# -----------------------------------------------------------------------------
# Configuration (edit if necessary)
# -----------------------------------------------------------------------------
BASE_PER_PCAP = "per_pcap_csvs"   # where per-pcap CSV folders live (input)
OUT_MERGED = "merged"             # per-pcap merged event timelines (output)
OUT_ALL_EVENTS = "all_events.csv" # concatenated big event CSV
OUT_SYNTH_PCAPS = "synth_pcaps"   # folder for generated pcaps (optional)
# -----------------------------------------------------------------------------

def ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)

# ----------------------------
# Step 1: Merge per-pcap csvs
# ----------------------------
def normalize_df(df: pd.DataFrame, event_type: str) -> pd.DataFrame:
    """
    Normalize a parsed per-log dataframe:
     - rename fields to prefix with event_type__ except 'ts' and 'uid'
     - create normalized 'ts' (float) if a timestamp column exists
     - ensure 'uid' column exists (string)
    """
    if df is None or df.shape[0] == 0:
        return pd.DataFrame()

    # find candidate ts column
    ts_candidates = [c for c in df.columns if c.lower() in ('ts','time','timestamp','ts_epoch','start_time')]
    tscol = ts_candidates[0] if ts_candidates else None

    # rename columns except ts and uid
    rename_map = {}
    for c in df.columns:
        if c == tscol or c.lower() == 'uid':
            rename_map[c] = c
        else:
            # avoid clobbering common names we want kept; still prefix to avoid collisions
            rename_map[c] = f"{event_type}__{c}"

    df = df.rename(columns=rename_map)

    # normalize ts
    if tscol:
        try:
            df['ts'] = pd.to_numeric(df[tscol], errors='coerce')
        except Exception:
            df['ts'] = pd.NA
    else:
        df['ts'] = pd.NA

    # ensure uid
    if 'uid' in df.columns:
        df['uid'] = df['uid'].astype(str)
    else:
        df['uid'] = ""

    return df

def merge_per_pcap(base_dir=BASE_PER_PCAP, out_dir=OUT_MERGED):
    """
    Walk base_dir which should contain per-pcap csvs arranged as:
      <base_dir>/<CLASS>/<SEQ>/<DEVICE>/*.csv
    For each device folder produce merged/<CLASS>_<SEQ>_<DEVICE>.csv containing an
    event timeline sorted by ts.
    """
    base = Path(base_dir)
    if not base.exists():
        print(f"ERROR: base per-pcap dir '{base_dir}' not found.")
        return []

    ensure_dir(out_dir)
    merged_paths = []

    for class_dir in sorted(base.iterdir()):
        if not class_dir.is_dir():
            continue
        for seq_dir in sorted(class_dir.iterdir()):
            if not seq_dir.is_dir():
                continue
            for device_dir in sorted(seq_dir.iterdir()):
                if not device_dir.is_dir():
                    continue
                pcap_id = f"{class_dir.name}_{seq_dir.name}_{device_dir.name}"
                print(f"Merging logs for {pcap_id} ...")
                merged_df = None
                event_counter = 0

                # load all csvs in this folder
                csv_files = sorted(device_dir.glob("*.csv"))
                if not csv_files:
                    print(f"  No CSV files in {device_dir}; skipping.")
                    continue

                for csv_path in csv_files:
                    event_type = csv_path.stem  # example: conn, dns, http
                    try:
                        df = pd.read_csv(csv_path)
                    except Exception as e:
                        print(f"  WARNING: unable to read {csv_path}: {e}; skipping.")
                        continue
                    ndf = normalize_df(df, event_type)
                    if ndf.empty:
                        continue

                    # add per-event uniform columns
                    ndf['pcap_id'] = pcap_id
                    ndf['attack'] = class_dir.name
                    ndf['count'] = seq_dir.name
                    ndf['path'] = device_dir.name
                    ndf['event_type'] = event_type
                    # prefix uids (avoid collisions across pcaps)
                    ndf['uid'] = ndf['uid'].apply(lambda x: f"{pcap_id}__{x}" if str(x).strip() != "" else "")
                    # event id
                    ndf['event_id'] = [f"{pcap_id}__evt_{event_counter + i}" for i in range(len(ndf))]
                    event_counter += len(ndf)

                    # append
                    if merged_df is None:
                        merged_df = ndf
                    else:
                        merged_df = pd.concat([merged_df, ndf], ignore_index=True, sort=False)

                if merged_df is None or merged_df.empty:
                    print(f"  No events merged for {pcap_id}.")
                    continue

                # sort by ts (nulls last)
                # ensure ts numeric
                merged_df['ts'] = pd.to_numeric(merged_df['ts'], errors='coerce')
                merged_df = merged_df.sort_values(by=['ts']).reset_index(drop=True)

                out_path = Path(out_dir) / f"{pcap_id}.csv"
                merged_df.to_csv(out_path, index=False)
                merged_paths.append(str(out_path))
                print(f"  Wrote merged timeline: {out_path} ({len(merged_df)} events)")

    return merged_paths

# -----------------------------------------
# Step 2: Concatenate all merged CSVs
# -----------------------------------------
def concat_merged(merged_dir=OUT_MERGED, out_csv=OUT_ALL_EVENTS):
    merged_dir = Path(merged_dir)
    if not merged_dir.exists():
        print(f"ERROR: merged dir '{merged_dir}' not found.")
        return None

    dfs = []
    for p in sorted(merged_dir.glob("*.csv")):
        try:
            df = pd.read_csv(p)
            dfs.append(df)
            print(f"  loaded {p} ({len(df)} rows)")
        except Exception as e:
            print(f"  skip {p}: {e}")

    if not dfs:
        print("No merged CSVs to concatenate.")
        return None

    big = pd.concat(dfs, ignore_index=True, sort=False)
    big.to_csv(out_csv, index=False)
    print(f"Wrote concatenated all-events CSV: {out_csv} ({len(big)} rows)")
    return out_csv

# -----------------------------------------
# Step 3: Simple pcapizer (starter)
# -----------------------------------------
def chunk_sizes(total_bytes, mean_pkt=400, mtu=1400):
    """Return a list of packet sizes that sum approximately to total_bytes."""
    sizes = []
    remaining = max(0, int(total_bytes))
    # handle 0 quickly
    if remaining == 0:
        return []
    while remaining > 0:
        # sample
        s = int(max(40, min(mtu, random.gauss(mean_pkt, mean_pkt*0.5))))
        if s <= 0:
            s = min(remaining, mtu)
        if s > remaining:
            s = remaining
        sizes.append(s)
        remaining -= s
    return sizes

def anon_to_ip(token):
    """Deterministic small IPv4 from anon token for stable mapping."""
    if not token or token == "nan":
        return "10.0.0.1"
    h = abs(hash(token))
    return f"10.{(h>>16)&255}.{(h>>8)&255}.{h&255}"

def synthesize_pcap_from_merged_csv(merged_csv_path, out_pcap_dir=OUT_SYNTH_PCAPS):
    """
    Read a merged timeline CSV and synthesize a PCAP. Uses conn events primarily.
    Conservative: creates TCP/UDP packets with random payloads sized to orig_bytes/resp_bytes.
    """
    try:
        df = pd.read_csv(merged_csv_path)
    except Exception as e:
        print(f"ERROR reading merged CSV {merged_csv_path}: {e}")
        return None

    # Import scapy lazily (only when synth requested)
    try:
        from scapy.all import Ether, IP, TCP, UDP, Raw, wrpcap
    except Exception as e:
        print("ERROR: scapy not available or failed to import. Install with: pip install scapy")
        return None

    pcap_id = df['pcap_id'].iloc[0] if 'pcap_id' in df.columns and not df.empty else Path(merged_csv_path).stem
    out_pcap_path = Path(out_pcap_dir) / f"{pcap_id}_synth.pcap"
    ensure_dir(out_pcap_dir)

    # Filter conn event rows (common event type) — fallback: look for 'conn' event_type rows
    if 'event_type' in df.columns:
        conn_rows = df[df['event_type'] == 'conn']
    else:
        # try to find conn-like columns
        conn_rows = df[[c for c in df.columns if 'conn' in c.lower() or c.lower().startswith('conn__')]].head(0)

    packets = []
    for idx, row in conn_rows.iterrows():
        # extract protocol / bytes fields robustly (try both raw and prefixed names)
        proto = None
        for cand in ['proto', 'conn__proto', 'conn__proto_x', 'conn__proto_y']:
            if cand in row and pd.notna(row[cand]):
                proto = str(row[cand]).lower()
                break
        if not proto:
            proto = 'tcp'

        # read byte counts
        def read_int_field(names, default=0):
            for n in names:
                if n in row and pd.notna(row[n]) and str(row[n]) != "-":
                    try:
                        return int(float(row[n]))
                    except:
                        continue
            return default

        orig_bytes = read_int_field(['orig_bytes', 'conn__orig_bytes'])
        resp_bytes = read_int_field(['resp_bytes', 'conn__resp_bytes'])

        # timestamp for flow (use ts if present)
        ts = None
        for t_cand in ['ts', 'conn__ts', 'time']:
            if t_cand in row and pd.notna(row[t_cand]):
                try:
                    ts = float(row[t_cand])
                    break
                except:
                    ts = None

        src_anon = row.get('id.orig_h_anon') or row.get('conn__id.orig_h_anon') or row.get('id.orig_h') or ""
        dst_anon = row.get('id.resp_h_anon') or row.get('conn__id.resp_h_anon') or row.get('id.resp_h') or ""

        src_ip = anon_to_ip(src_anon)
        dst_ip = anon_to_ip(dst_anon)

        # chunk sizes
        orig_pkt_sizes = chunk_sizes(orig_bytes)
        resp_pkt_sizes = chunk_sizes(resp_bytes)

        # create simplistic packets
        t = ts if ts is not None else (random.random() * 1000)
        # generate orig-direction packets
        for s in orig_pkt_sizes:
            if proto.startswith('udp'):
                pkt = Ether()/IP(src=src_ip, dst=dst_ip)/UDP(sport=random.randint(1024, 65000), dport=random.randint(1, 65535))/Raw(load=bytes([random.randint(0,255) for _ in range(max(s-40, 0))]))
            else:
                pkt = Ether()/IP(src=src_ip, dst=dst_ip)/TCP(sport=random.randint(1024, 65000), dport=random.randint(1,65535), flags="PA")/Raw(load=bytes([random.randint(0,255) for _ in range(max(s-54, 0))]))
            pkt.time = t
            packets.append(pkt)
            # increment time
            t += max(0.0001, random.expovariate(1.0/0.01))
        # small pause then resp
        t += 0.001
        for s in resp_pkt_sizes:
            if proto.startswith('udp'):
                pkt = Ether()/IP(src=dst_ip, dst=src_ip)/UDP(sport=random.randint(1024, 65000), dport=random.randint(1,65535))/Raw(load=bytes([random.randint(0,255) for _ in range(max(s-40,0))]))
            else:
                pkt = Ether()/IP(src=dst_ip, dst=src_ip)/TCP(sport=random.randint(1024, 65000), dport=random.randint(1,65535), flags="PA")/Raw(load=bytes([random.randint(0,255) for _ in range(max(s-54,0))]))
            pkt.time = t
            packets.append(pkt)
            t += max(0.0001, random.expovariate(1.0/0.01))

    # write pcap if any packets
    if packets:
        try:
            wrpcap(str(out_pcap_path), packets)
            print(f"Wrote synthesized pcap {out_pcap_path} (packets: {len(packets)})")
            return str(out_pcap_path)
        except Exception as e:
            print(f"ERROR writing pcap {out_pcap_path}: {e}")
            return None
    else:
        print(f"No conn events found in {merged_csv_path} -> no pcap created.")
        return None

def synthesize_all_merged(merged_dir=OUT_MERGED, out_pcap_dir=OUT_SYNTH_PCAPS):
    merged_dir = Path(merged_dir)
    ensure_dir(out_pcap_dir)
    for p in sorted(merged_dir.glob("*.csv")):
        print("Synthesizing pcap for", p)
        synth_path = synthesize_pcap_from_merged_csv(str(p), out_pcap_dir)
        if synth_path:
            print("  done:", synth_path)

# -------------------------
# CLI
# -------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Merge Zeek-per-pcap CSVs, concat, and optionally synthesize pcaps.")
    p.add_argument("--merge", action="store_true", help="Merge per-pcap CSV logs into merged/<pcap>.csv")
    p.add_argument("--concat", action="store_true", help="Concatenate merged CSVs into all_events.csv")
    p.add_argument("--synthesize", action="store_true", help="Synthesize PCAPs from merged timelines (requires scapy)")
    p.add_argument("--base", default=BASE_PER_PCAP, help="Base per-pcap folder (default: per_pcap_csvs)")
    p.add_argument("--merged_out", default=OUT_MERGED, help="Merged per-pcap output dir (default: merged)")
    p.add_argument("--all_events", default=OUT_ALL_EVENTS, help="All-events CSV output (default: all_events.csv)")
    p.add_argument("--synth_out", default=OUT_SYNTH_PCAPS, help="Synth PCAP output dir (default: synth_pcaps)")
    return p.parse_args()

def main():
    args = parse_args()
    if not (args.merge or args.concat or args.synthesize):
        print("No action chosen. Use --merge and/or --concat and/or --synthesize. Exiting.")
        return

    merged_paths = []
    if args.merge:
        print("==> Step 1: merge per-pcap csvs ...")
        merged_paths = merge_per_pcap(base_dir=args.base, out_dir=args.merged_out)

    if args.concat:
        print("==> Step 2: concat merged into big CSV ...")
        concat_path = concat_merged(merged_dir=args.merged_out, out_csv=args.all_events)
        if concat_path:
            print(f"All events concatenated to: {concat_path}")

    if args.synthesize:
        print("==> Step 3: synthesize PCAPs for merged timelines ...")
        synthesize_all_merged(merged_dir=args.merged_out, out_pcap_dir=args.synth_out)

if __name__ == "__main__":
    main()
