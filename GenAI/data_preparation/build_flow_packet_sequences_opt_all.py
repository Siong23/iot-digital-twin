#!/usr/bin/env python3
"""
build_flow_packet_sequences_opt_all.py

Process ALL packet CSVs in dataset/processed_dataset/packets/*.csv and produce
dataset/processed_dataset/seqs/<PCAP_ID>_seqs.jsonl

Features:
 - Build a conn.csv map once (from per_pcap_csvs).
 - Chunked reading of packet CSVs to avoid memory blowups.
 - Per-UID temporary ndjson to avoid huge in-memory dicts.
 - Resume support: skip already-existing output files.
 - Tunable chunksize and tmp dir.

Usage:
  python3 build_flow_packet_sequences_opt_all.py
  python3 build_flow_packet_sequences_opt_all.py --chunksize 100000 --clean-tmp

"""
import argparse, json, time, sys
from pathlib import Path
from collections import defaultdict
import pandas as pd

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--packets-dir", default="dataset/processed_dataset/packets")
    p.add_argument("--conn-root", default="dataset/processed_dataset/per_pcap_csvs")
    p.add_argument("--out-dir", default="dataset/processed_dataset/seqs")
    p.add_argument("--tmp-dir", default="dataset/processed_dataset/seqs_tmp")
    p.add_argument("--chunksize", type=int, default=200000)
    p.add_argument("--clean-tmp", action="store_true", help="Remove tmp per-uid files after assembling final jsonl (saves disk).")
    p.add_argument("--force", action="store_true", help="Reprocess even if output exists.")
    return p.parse_args()

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def safe_str(x):
    return "" if pd.isna(x) else str(x)

def parse_port_field(val):
    if val is None:
        return ""
    v = str(val).strip()
    if v == "-" or v == "":
        return ""
    try:
        if "." in v:
            v_f = float(v); v_i = int(v_f); return str(v_i)
        return v
    except:
        return v

def build_flow_index_from_conn(conn_df):
    key_map = defaultdict(list)
    flows_meta = {}
    for idx, row in conn_df.iterrows():
        uid = safe_str(row.get("uid","")).strip()
        if uid == "": continue
        orig_h = safe_str(row.get("id.orig_h", row.get("orig_h",""))).strip()
        resp_h = safe_str(row.get("id.resp_h", row.get("resp_h",""))).strip()
        orig_p = parse_port_field(row.get("id.orig_p", row.get("orig_p","")))
        resp_p = parse_port_field(row.get("id.resp_p", row.get("resp_p","")))
        proto = safe_str(row.get("proto", row.get("conn__proto","tcp"))).lower().strip()
        start_ts = None
        try:
            if "ts" in row and not pd.isna(row["ts"]): start_ts = float(row["ts"])
            elif "start_time" in row and not pd.isna(row["start_time"]): start_ts = float(row["start_time"])
        except:
            start_ts = None
        duration = 0.0
        try:
            if "duration" in row and not pd.isna(row["duration"]): duration = float(row["duration"])
        except:
            duration = 0.0
        end_ts = (start_ts + duration) if (start_ts is not None and duration>0) else (start_ts + 3600.0 if start_ts is not None else None)
        meta = {"uid": uid, "orig_h": orig_h, "resp_h": resp_h, "orig_p": orig_p, "resp_p": resp_p, "proto": proto, "start_ts": start_ts, "end_ts": end_ts}
        flows_meta[uid] = meta
        key_map[(orig_h, resp_h, orig_p, resp_p, proto)].append(meta)
        key_map[(resp_h, orig_h, resp_p, orig_p, proto)].append(meta)
        key_map[(orig_h, resp_h, "", "", proto)].append(meta)
        key_map[(resp_h, orig_h, "", "", proto)].append(meta)
    return key_map, flows_meta

def match_packet_to_flow(packet_row, key_map):
    ip_src = safe_str(packet_row.get("ip_src","")).strip()
    ip_dst = safe_str(packet_row.get("ip_dst","")).strip()
    tcp_src = parse_port_field(packet_row.get("tcp_srcport",""))
    tcp_dst = parse_port_field(packet_row.get("tcp_dstport",""))
    udp_src = parse_port_field(packet_row.get("udp_srcport",""))
    udp_dst = parse_port_field(packet_row.get("udp_dstport",""))
    frame_time = None
    try:
        frame_time = float(packet_row.get("time_epoch")) if packet_row.get("time_epoch") not in (None,"","nan") else None
    except:
        frame_time = None
    if tcp_src != "" or tcp_dst != "":
        src_port, dst_port, proto = tcp_src, tcp_dst, "tcp"
    elif udp_src != "" or udp_dst != "":
        src_port, dst_port, proto = udp_src, udp_dst, "udp"
    else:
        src_port, dst_port, proto = "", "", "ip"
    key = (ip_src, ip_dst, src_port, dst_port, proto)
    candidates = key_map.get(key, [])
    if not candidates:
        rkey = (ip_dst, ip_src, dst_port, src_port, proto)
        candidates = key_map.get(rkey, [])
    if not candidates:
        key_relaxed = (ip_src, ip_dst, "", "", proto)
        candidates = key_map.get(key_relaxed, [])
        if not candidates:
            rkey_relaxed = (ip_dst, ip_src, "", "", proto)
            candidates = key_map.get(rkey_relaxed, [])
    if not candidates:
        return None
    if frame_time is not None:
        for f in candidates:
            if f["start_ts"] is not None and f["end_ts"] is not None and f["start_ts"] <= frame_time <= f["end_ts"]:
                return f["uid"]
        best = min(candidates, key=lambda x: abs((x["start_ts"] or 0.0) - (frame_time or 0.0)))
        return best["uid"]
    else:
        return candidates[0]["uid"]

def build_conn_map(conn_root: Path):
    conn_map = {}
    for c in conn_root.rglob("conn.csv"):
        parts = c.parts
        if 'per_pcap_csvs' in parts:
            try:
                idx = parts.index('per_pcap_csvs')
                cls = parts[idx+1]; seq = parts[idx+2]; device = parts[idx+3]
                pcap_id = f"{cls}_{seq}_{device}"
                conn_map[pcap_id] = c
            except Exception:
                # skip malformed paths
                continue
    return conn_map

def process_one(pcap_id, pkt_csv, conn_csv, out_dir: Path, tmp_dir: Path, chunksize: int, clean_tmp: bool):
    out_path = out_dir / f"{pcap_id}_seqs.jsonl"
    if out_path.exists():
        print(f"Skipping {pcap_id} (output exists)"); return
    print(f"\n=== Processing {pcap_id} ===")
    try:
        conn_df = pd.read_csv(conn_csv, low_memory=False, dtype=str)
    except Exception as e:
        print("  Failed reading conn.csv:", e); return
    key_map, flows_meta = build_flow_index_from_conn(conn_df)
    print(f"  flows index built: {len(flows_meta)} flows")
    tmp_uid_dir = tmp_dir / pcap_id
    ensure_dir(tmp_uid_dir)
    total_packets = 0
    try:
        for chunk_no, chunk in enumerate(pd.read_csv(pkt_csv, chunksize=chunksize, low_memory=False)):
            print(f"  chunk {chunk_no} rows={len(chunk)}")
            for _, prow in chunk.iterrows():
                total_packets += 1
                pr = {
                    "ip_src": prow.get("ip_src",""),
                    "ip_dst": prow.get("ip_dst",""),
                    "tcp_srcport": prow.get("tcp_srcport",""),
                    "tcp_dstport": prow.get("tcp_dstport",""),
                    "udp_srcport": prow.get("udp_srcport",""),
                    "udp_dstport": prow.get("udp_dstport",""),
                    "time_epoch": prow.get("time_epoch",""),
                    "frame_len": prow.get("frame_len",""),
                    "tcp_retrans": prow.get("tcp_retrans",""),
                    "tcp_dup_ack": prow.get("tcp_dup_ack",""),
                    "ip_mf": prow.get("ip_mf",""),
                    "tcp_flags": prow.get("tcp_flags","")
                }
                uid = match_packet_to_flow(pr, key_map)
                if uid is None: continue
                try:
                    ts = float(pr["time_epoch"]) if pr["time_epoch"] not in (None,"","nan") else None
                except:
                    ts = None
                pkt_rec = {"ts": ts, "size": int(float(pr["frame_len"])) if pr["frame_len"] not in (None,"","") else 0, "flags": pr.get("tcp_flags",""), "direction": None}
                fmeta = flows_meta.get(uid)
                if fmeta: pkt_rec["direction"] = 0 if pr["ip_src"] == fmeta["orig_h"] else 1
                tuf = tmp_uid_dir / f"{uid}.ndjson"
                with open(tuf, "a") as fo:
                    fo.write(json.dumps(pkt_rec) + "\n")
    except Exception as e:
        print("  Error processing packets:", e); return
    print(f"  Done scanning packets (total processed {total_packets}). Assembling output...")
    # assemble jsonl
    ensure_dir(out_dir)
    with open(out_path, "w") as fo:
        for tuf in sorted(tmp_uid_dir.glob("*.ndjson")):
            uid = tuf.stem
            pkts = []
            with open(tuf, "r") as fi:
                for line in fi:
                    try:
                        pkts.append(json.loads(line))
                    except:
                        pass
            if not pkts: continue
            pkts = sorted(pkts, key=lambda x: x["ts"] or 0)
            times = [p["ts"] or 0 for p in pkts]
            iats = [(times[i] - times[i-1]) if i>0 else 0 for i in range(len(times))]
            for i,p in enumerate(pkts):
                p["iat"] = iats[i]
            rec = {"pcap_id": pcap_id, "uid": uid, "packets": pkts}
            fo.write(json.dumps(rec) + "\n")
    print("  Wrote:", out_path)
    if clean_tmp:
        for tuf in tmp_uid_dir.glob("*.ndjson"):
            try: tuf.unlink()
            except: pass
        try: tmp_uid_dir.rmdir()
        except: pass
    print(f"Finished {pcap_id}")

def main():
    args = parse_args()
    packets_dir = Path(args.packets_dir)
    conn_root = Path(args.conn_root)
    out_dir = Path(args.out_dir)
    tmp_dir = Path(args.tmp_dir)
    ensure_dir(out_dir); ensure_dir(tmp_dir)
    print("Building conn map...")
    conn_map = build_conn_map(conn_root)
    print(f"Found {len(conn_map)} conn.csv entries in {conn_root}")

    packet_files = sorted(Path(args.packets_dir).glob("packets_*.csv"))
    print(f"Found {len(packet_files)} packet CSVs in {packets_dir}")

    for pktf in packet_files:
        pcap_id = pktf.stem.replace("packets_","")
        # find conn path
        conn_csv = conn_map.get(pcap_id)
        if conn_csv is None:
            # try substring match
            for k,v in conn_map.items():
                if pcap_id in k:
                    conn_csv = v
                    break
        if conn_csv is None:
            print(f"WARNING: no conn.csv found for {pcap_id}; skipping")
            continue
        out_path = out_dir / f"{pcap_id}_seqs.jsonl"
        if out_path.exists() and not args.force:
            print(f"Skipping {pcap_id} (already processed). Use --force to re-run.")
            continue
        process_one(pcap_id, pktf, conn_csv, out_dir, tmp_dir, args.chunksize, args.clean_tmp)

if __name__ == "__main__":
    main()

