#!/usr/bin/env python3
"""
zeek_to_csv.py

Convert per-pcap Zeek log folders organized as:
  <BASE_DIR>/<CLASS>/<SEQ>/<DEVICE>/zeek_logs/*.log

into:
  processed_dataset/
    per_pcap_csvs/<CLASS>/<SEQ>/<DEVICE>/conn.csv, dns.csv, ...
    manifests/pcaps_manifest.csv
    all_flows.parquet
    manifests/ip_map.json
    device_profiles.csv

Notes:
 - This script parses Zeek logs by reading the "#fields" header line and splitting data rows on tabs.
 - It focuses on flow/app-level features (no packet-level aggregates, since PCAPs are not required).
 - If you have PCAPs and want per-packet stats (pkt-size percentiles, iat, retransmits), ask for an extension.
"""

import os
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import pandas as pd
import sys

# === CONFIG ===
BASE_DIR = "./ZEEK_LOGS"        # <-- set to the parent directory containing Brute-force/, DDoS/, etc.
OUT_DIR = "./processed_dataset" # output root
PER_PCAP_DIR = os.path.join(OUT_DIR, "per_pcap_csvs")
MANIFESTS_DIR = os.path.join(OUT_DIR, "manifests")
ALL_FLOWS_PATH = os.path.join(OUT_DIR, "all_flows.parquet")
DEVICE_PROFILES_PATH = os.path.join(OUT_DIR, "device_profiles.csv")

# Map Zeek log filenames to desired CSV names (if present)
LOGS_TO_EXTRACT = {
    "conn.log": "conn.csv",
    "dns.log": "dns.csv",
    "http.log": "http.csv",
    "ssl.log": "tls.csv",
    "tls.log": "tls.csv",
    "files.log": "files.csv",
    "notice.log": "notice.csv",
    "weird.log": "weird.csv",
    "dhcp.log": "dhcp.csv",
    "mqtt_connect.log": "mqtt_connect.csv",
    "mqtt_publish.log": "mqtt_publish.csv",
    "mqtt_subcribe.log": "mqtt_subscribe.csv",  # accommodate misspelling
    "mqtt_subscribe.log": "mqtt_subscribe.csv",
    "capture_loss.log": "capture_loss.csv",
    "stats.log": "stats.csv",
    "telemetry.log": "telemetry.csv"
}

# === Helpers ===

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def parse_zeek_log_to_df(logpath):
    """
    Parse a Zeek log into a pandas DataFrame using the "#fields" header.
    If no #fields found, returns an empty DataFrame.
    """
    cols = None
    records = []
    try:
        with open(logpath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                if line.startswith("#fields"):
                    parts = line.split("\t")
                    cols = parts[1:]
                    continue
                if line.startswith("#"):
                    continue
                # data row
                vals = line.split("\t")
                if cols is None:
                    # can't parse reliably without header
                    continue
                # pad/truncate
                if len(vals) < len(cols):
                    vals += [""] * (len(cols) - len(vals))
                records.append(vals[:len(cols)])
    except Exception as e:
        print("ERROR reading", logpath, ":", e)
        return pd.DataFrame()

    if cols is None:
        return pd.DataFrame()

    try:
        df = pd.DataFrame(records, columns=cols)
    except Exception:
        # fallback tolerant construction
        df = pd.DataFrame(records)
        df.columns = cols[:df.shape[1]]
    return df

def infer_pcap_id_from_path(zeek_logs_folder):
    """
    Given a path ending with .../<CLASS>/<SEQ>/<DEVICE>/zeek_logs,
    return (cls, seq, device, pcap_id).
    """
    p = Path(zeek_logs_folder).resolve()
    parts = p.parts
    if "zeek_logs" in parts:
        idx = parts.index("zeek_logs")
        if idx >= 3:
            cls = parts[idx-3]
            seq = parts[idx-2]
            device = parts[idx-1]
            pcap_id = f"{cls}_{seq}_{device}"
            return (cls, seq, device, pcap_id)
    # fallback use last 4
    tail = parts[-4:]
    if len(tail) >= 3:
        cls, seq, device = tail[0], tail[1], tail[2]
        pcap_id = f"{cls}_{seq}_{device}"
        return (cls, seq, device, pcap_id)
    return ("unknown","0","unknown","unknown_0_unknown")

def save_df_csv(df, outpath):
    ensure_dir(os.path.dirname(outpath))
    try:
        df.to_csv(outpath, index=False)
    except Exception as e:
        # last-resort: write with utf-8 and simple quoting
        df.to_csv(outpath, index=False, encoding="utf-8", errors="replace")
    print(f"Wrote {outpath} ({len(df)} rows)")

# === Main processing ===

def main():
    base = Path(BASE_DIR)
    if not base.exists():
        print("ERROR: BASE_DIR does not exist:", BASE_DIR)
        sys.exit(1)

    ensure_dir(OUT_DIR)
    ensure_dir(PER_PCAP_DIR)
    ensure_dir(MANIFESTS_DIR)

    pcaps_manifest_rows = []
    all_flows_rows = []
    ip_map = {}
    ip_counter = 0

    # iterate over all zeek_logs directories recursively
    for zeek_logs_dir in sorted(base.rglob("zeek_logs")):
        if not zeek_logs_dir.is_dir():
            continue
        cls, seq, device, pcap_id = infer_pcap_id_from_path(str(zeek_logs_dir))
        out_pcap_dir = Path(PER_PCAP_DIR) / cls / seq / device
        ensure_dir(out_pcap_dir)

        log_files = sorted([f for f in os.listdir(zeek_logs_dir) if f.endswith(".log")])
        print("\nProcessing:", zeek_logs_dir, "-> pcap_id=", pcap_id, "; found", len(log_files), ".log files")

        manifest_row = {
            "pcap_id": pcap_id,
            "class": cls,
            "seq": seq,
            "device": device,
            "zeek_log_dir": str(zeek_logs_dir),
            "num_logs": len(log_files)
        }

        parsed = {}
        # parse logs
        for lf in log_files:
            lfpath = zeek_logs_dir / lf
            df = parse_zeek_log_to_df(str(lfpath))
            if df.empty:
                # still create an empty csv to mark presence (optional)
                parsed[lf] = pd.DataFrame()
                continue
            # attach metadata columns
            df['pcap_id'] = pcap_id
            df['orig_class'] = cls
            df['orig_device'] = device
            # determine out filename
            outname = LOGS_TO_EXTRACT.get(lf, lf + ".csv")
            outpath = out_pcap_dir / outname
            save_df_csv(df, str(outpath))
            parsed[lf] = df

        # manifest: try extracting time range and flow counts from conn.log
        if "conn.log" in parsed and not parsed["conn.log"].empty:
            cdf = parsed["conn.log"]
            # ts is usually 'ts' field
            ts_col = None
            for candidate in ('ts','start_time','ts_start'):
                if candidate in cdf.columns:
                    ts_col = candidate
                    break
            try:
                if ts_col:
                    # convert to float safely
                    tsvals = pd.to_numeric(cdf[ts_col], errors='coerce').dropna()
                    if not tsvals.empty:
                        t0 = float(tsvals.min())
                        t1 = float(tsvals.max())
                        manifest_row['start_time_epoch'] = t0
                        manifest_row['end_time_epoch'] = t1
                        manifest_row['duration_s'] = t1 - t0
                manifest_row['num_flows'] = len(cdf)
            except Exception as e:
                print("Warning: manifest extraction from conn.log failed:", e)
                manifest_row['start_time_epoch'] = None
                manifest_row['end_time_epoch'] = None
                manifest_row['duration_s'] = None
                manifest_row['num_flows'] = len(cdf)
        else:
            manifest_row['start_time_epoch'] = None
            manifest_row['end_time_epoch'] = None
            manifest_row['duration_s'] = None
            manifest_row['num_flows'] = 0

        pcaps_manifest_rows.append(manifest_row)

        # === build per-flow enriched rows based on conn.log ===
        if "conn.log" in parsed and not parsed["conn.log"].empty:
            cdf = parsed["conn.log"].copy()
            # ensure uid column
            if 'uid' not in cdf.columns:
                # create a synthetic uid from 5-tuple and ts (best-effort)
                def make_uid(r):
                    try:
                        return "uid_" + str(abs(hash((str(r.get('id.orig_h','')), str(r.get('id.resp_h','')),
                                                     str(r.get('id.orig_p','')), str(r.get('id.resp_p','')),
                                                     str(r.get('ts',''))))))[:24]
                    except Exception:
                        return ""
                cdf['uid'] = cdf.apply(make_uid, axis=1)

            # guarantee presence of key columns
            keep_cols = ['pcap_id','uid','ts','id.orig_h','id.resp_h','id.orig_p','id.resp_p','proto','service',
                         'duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes','conn_state','history']
            for col in keep_cols:
                if col not in cdf.columns:
                    cdf[col] = None

            # append per-flow dicts
            idx_start = len(all_flows_rows)
            for _, row in cdf.iterrows():
                flow = {k: row.get(k, None) for k in keep_cols}
                # anonymize ips (simple mapping)
                for ipcol in ('id.orig_h', 'id.resp_h'):
                    ip = flow.get(ipcol, None)
                    if ip and ip != "-" and pd.notna(ip):
                        if ip not in ip_map:
                            ip_counter = len(ip_map) + 1
                            ip_map[ip] = f"dev_{ip_counter}"
                        flow[ipcol + "_anon"] = ip_map.get(ip)
                        # preserve /24 prefix when IPv4-like
                        try:
                            parts = str(ip).split(".")
                            if len(parts) == 4:
                                flow[ipcol + "_p24"] = ".".join(parts[:3]) + ".0/24"
                            else:
                                flow[ipcol + "_p24"] = None
                        except Exception:
                            flow[ipcol + "_p24"] = None
                    else:
                        flow[ipcol + "_anon"] = None
                        flow[ipcol + "_p24"] = None
                flow['pcap_id'] = pcap_id
                flow['class'] = cls
                flow['device'] = device
                # zeroed enrichment fields to be filled below
                flow.update({
                    'dns_q_count': 0,
                    'http_count': 0,
                    'tls_count': 0,
                    'files_count': 0,
                    'mqtt_pub_count': 0,
                    'notice_count': 0
                })
                all_flows_rows.append(flow)

            # build uid -> index map for the appended flows
            uid_to_idx = {}
            for i, r in enumerate(cdf['uid'].tolist(), start=idx_start):
                if r:
                    uid_to_idx[r] = i

            # enrichment: aggregate other parsed logs by uid and attach counts
            # DNS
            if "dns.log" in parsed and not parsed["dns.log"].empty:
                ddf = parsed["dns.log"]
                if 'uid' in ddf.columns:
                    dns_counts = ddf.groupby('uid').size().to_dict()
                    for uid,cnt in dns_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows[uid_to_idx[uid]]['dns_q_count'] = int(cnt)
            # HTTP
            if "http.log" in parsed and not parsed["http.log"].empty:
                hdf = parsed["http.log"]
                if 'uid' in hdf.columns:
                    http_counts = hdf.groupby('uid').size().to_dict()
                    for uid,cnt in http_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows[uid_to_idx[uid]]['http_count'] = int(cnt)
            # TLS / SSL
            if ("tls.log" in parsed and not parsed["tls.log"].empty) or ("ssl.log" in parsed and not parsed["ssl.log"].empty):
                tkey = "tls.log" if "tls.log" in parsed and not parsed["tls.log"].empty else "ssl.log"
                tdf = parsed[tkey]
                if 'uid' in tdf.columns:
                    tls_counts = tdf.groupby('uid').size().to_dict()
                    for uid,cnt in tls_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows[uid_to_idx[uid]]['tls_count'] = int(cnt)
            # FILES
            if "files.log" in parsed and not parsed["files.log"].empty:
                fdf = parsed["files.log"]
                if 'uid' in fdf.columns:
                    f_counts = fdf.groupby('uid').size().to_dict()
                    for uid,cnt in f_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows[uid_to_idx[uid]]['files_count'] = int(cnt)
            # MQTT publish
            if "mqtt_publish.log" in parsed and not parsed["mqtt_publish.log"].empty:
                mdf = parsed["mqtt_publish.log"]
                if 'uid' in mdf.columns:
                    m_counts = mdf.groupby('uid').size().to_dict()
                    for uid,cnt in m_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows[uid_to_idx[uid]]['mqtt_pub_count'] = int(cnt)
            # Notices
            if "notice.log" in parsed and not parsed["notice.log"].empty:
                ndf = parsed["notice.log"]
                if 'uid' in ndf.columns:
                    n_counts = ndf.groupby('uid').size().to_dict()
                    for uid,cnt in n_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows[uid_to_idx[uid]]['notice_count'] = int(cnt)

        else:
            print(f"Warning: conn.log missing or empty for {pcap_id}, flow-level extraction skipped for this folder.")

    # end for each zeek_logs dir

    # write manifests
    pcaps_manifest_df = pd.DataFrame(pcaps_manifest_rows)
    manifest_path = os.path.join(MANIFESTS_DIR, "pcaps_manifest.csv")
    pcaps_manifest_df.to_csv(manifest_path, index=False)
    print("\nWrote pcaps manifest:", manifest_path)

    # write ip_map
    ip_map_path = os.path.join(MANIFESTS_DIR, "ip_map.json")
    with open(ip_map_path, "w") as f:
        json.dump(ip_map, f, indent=2)
    print("Wrote ip map:", ip_map_path)

    # assemble all_flows DataFrame and write parquet
    if len(all_flows_rows) > 0:
        flows_df = pd.DataFrame(all_flows_rows)
        # reorder columns with a reasonable default ordering
        cols_order = ['pcap_id','class','device','uid','ts','id.orig_h','id.orig_h_anon','id.orig_h_p24',
                      'id.resp_h','id.resp_h_anon','id.resp_h_p24','id.orig_p','id.resp_p','proto','service',
                      'duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes','conn_state','history',
                      'dns_q_count','http_count','tls_count','files_count','mqtt_pub_count','notice_count']
        cols_exist = [c for c in cols_order if c in flows_df.columns]
        flows_df = flows_df[cols_exist]
        ensure_dir(os.path.dirname(ALL_FLOWS_PATH))
        flows_df.to_parquet(ALL_FLOWS_PATH, index=False)
        print("Wrote merged flows parquet:", ALL_FLOWS_PATH)
    else:
        print("No flows collected; all_flows.parquet not created.")

    # produce device profiles from Normal class (simple heuristics)
    try:
        if os.path.exists(ALL_FLOWS_PATH):
            flows_df = pd.read_parquet(ALL_FLOWS_PATH)
            if 'class' in flows_df.columns:
                normal = flows_df[flows_df['class'].str.lower() == 'normal']
            else:
                normal = pd.DataFrame()
            if not normal.empty:
                profiles = []
                for device, g in normal.groupby('device'):
                    profile = {
                        'device': device,
                        'num_flows': int(len(g)),
                        'median_bytes_per_flow': float(g['orig_bytes'].dropna().astype(float).median()) if 'orig_bytes' in g.columns else None,
                        'median_duration_s': float(g['duration'].dropna().astype(float).median()) if 'duration' in g.columns else None,
                        'common_dst_p24': str(g['id.resp_h_p24'].value_counts().idxmax()) if 'id.resp_h_p24' in g.columns and not g['id.resp_h_p24'].isna().all() else None
                    }
                    profiles.append(profile)
                prof_df = pd.DataFrame(profiles)
                prof_df.to_csv(DEVICE_PROFILES_PATH, index=False)
                print("Wrote device profiles:", DEVICE_PROFILES_PATH)
            else:
                print("No Normal-class flows found; skipping device profile generation.")
    except Exception as e:
        print("Device profile generation failed:", e)

    print("\nProcessing complete. Output directory:", OUT_DIR)


if __name__ == "__main__":
    main()
