#!/usr/bin/env python3
"""
zeek_to_csv_resume.py

Resume-safe conversion of Zeek log folders (<BASE_DIR>/<CLASS>/<SEQ>/<DEVICE>/zeek_logs/*.log)
into per-pcap CSVs and a merged per-flow Parquet dataset.

Features:
 - If per-pcap CSV already exists, skip parsing that .log (resume-friendly).
 - If all_flows.parquet exists, load it and append only flows from pcap_ids not yet included.
 - Writes/updates manifests/pcaps_manifest.csv and manifests/ip_map.json incrementally.
 - Conservative parsing: uses Zeek "#fields" header lines to parse logs.
 - Does NOT compute packet-level aggregates (requires PCAP + tshark). Ask later if you want that.

Usage:
  * Set BASE_DIR to your zeek logs root (the parent of Brute-force/, DDoS/, ...)
  * Run: python3 zeek_to_csv_resume.py
"""

import os
import json
from pathlib import Path
import pandas as pd
import sys

# ------------------ CONFIG ------------------
BASE_DIR = "./ZEEK_LOGS"         # <-- set this to your root zeek logs folder
OUT_DIR = "./processed_dataset"  # output root
PER_PCAP_DIR = os.path.join(OUT_DIR, "per_pcap_csvs")
MANIFESTS_DIR = os.path.join(OUT_DIR, "manifests")
ALL_FLOWS_PATH = os.path.join(OUT_DIR, "all_flows.parquet")
PCAPS_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "pcaps_manifest.csv")
IP_MAP_PATH = os.path.join(MANIFESTS_DIR, "ip_map.json")
DEVICE_PROFILES_PATH = os.path.join(OUT_DIR, "device_profiles.csv")

# Map Zeek log filenames to CSV names
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
    "mqtt_subcribe.log": "mqtt_subscribe.csv",
    "mqtt_subscribe.log": "mqtt_subscribe.csv",
    "capture_loss.log": "capture_loss.csv",
    "stats.log": "stats.csv",
    "telemetry.log": "telemetry.csv"
}

# ------------------ HELPERS ------------------

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def parse_zeek_log_to_df(logpath):
    """
    Parse Zeek log to DataFrame using "#fields" header.
    Returns empty DataFrame if header not found or file empty.
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
                if cols is None:
                    # Can't parse without fields header; skip
                    continue
                vals = line.split("\t")
                if len(vals) < len(cols):
                    vals += [""] * (len(cols) - len(vals))
                records.append(vals[:len(cols)])
    except Exception as e:
        print("ERROR reading:", logpath, e)
        return pd.DataFrame()
    if cols is None:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(records, columns=cols)
    except Exception:
        df = pd.DataFrame(records)
        df.columns = cols[:df.shape[1]]
    return df

def infer_pcap_id_from_path(zeek_logs_folder):
    """
    Given path .../<CLASS>/<SEQ>/<DEVICE>/zeek_logs, return (cls, seq, device, pcap_id)
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
    # fallback: use last 3-4 components
    tail = parts[-4:]
    if len(tail) >= 3:
        cls, seq, device = tail[0], tail[1], tail[2]
        return (cls, seq, device, f"{cls}_{seq}_{device}")
    return ("unknown","0","unknown","unknown_0_unknown")

# ------------------ MAIN ------------------

def main():
    base = Path(BASE_DIR)
    if not base.exists():
        print("ERROR: BASE_DIR does not exist:", BASE_DIR)
        sys.exit(1)

    ensure_dir(OUT_DIR)
    ensure_dir(PER_PCAP_DIR)
    ensure_dir(MANIFESTS_DIR)

    # load existing manifests if present (for resume)
    if os.path.exists(PCAPS_MANIFEST_PATH):
        try:
            pcaps_manifest_df = pd.read_csv(PCAPS_MANIFEST_PATH)
            existing_pcaps = set(pcaps_manifest_df['pcap_id'].astype(str).tolist())
        except Exception:
            pcaps_manifest_df = pd.DataFrame()
            existing_pcaps = set()
    else:
        pcaps_manifest_df = pd.DataFrame()
        existing_pcaps = set()

    if os.path.exists(IP_MAP_PATH):
        try:
            with open(IP_MAP_PATH, "r") as f:
                ip_map = json.load(f)
        except Exception:
            ip_map = {}
    else:
        ip_map = {}

    # load existing merged flows if present (for resume / dedup)
    if os.path.exists(ALL_FLOWS_PATH):
        try:
            existing_flows_df = pd.read_parquet(ALL_FLOWS_PATH)
            existing_pcap_ids_in_flows = set(existing_flows_df['pcap_id'].astype(str).unique()) if 'pcap_id' in existing_flows_df.columns else set()
            print(f"Loaded existing all_flows.parquet ({len(existing_flows_df)} rows), pcaps in it: {len(existing_pcap_ids_in_flows)}")
        except Exception as e:
            print("Warning: failed to read existing all_flows.parquet:", e)
            existing_flows_df = pd.DataFrame()
            existing_pcap_ids_in_flows = set()
    else:
        existing_flows_df = pd.DataFrame()
        existing_pcap_ids_in_flows = set()

    all_flows_rows_new = []  # collect flows for pcaps not yet in existing_parquet
    pcaps_manifest_rows_new = []

    # iterate over all zeek_logs dirs
    for zeek_logs_dir in sorted(base.rglob("zeek_logs")):
        if not zeek_logs_dir.is_dir():
            continue
        cls, seq, device, pcap_id = infer_pcap_id_from_path(str(zeek_logs_dir))
        print("\n--- Processing zeek_logs folder:", zeek_logs_dir, "-> pcap_id:", pcap_id, "---")

        per_pcap_out_dir = Path(PER_PCAP_DIR) / cls / seq / device
        ensure_dir(per_pcap_out_dir)

        # find all .log files in this folder
        log_files = sorted([p for p in os.listdir(zeek_logs_dir) if p.endswith(".log")])
        print("Found .log files:", ", ".join(log_files))

        # If pcap_id already present in existing_parquet, we still want to ensure per-pcap CSVs exist, but we won't re-append flows.
        already_in_parquet = (pcap_id in existing_pcap_ids_in_flows)

        # parse/save logs (skip if target CSV already exists)
        parsed_logs = {}  # map from log filename -> DataFrame (loaded from CSV if exists, or parsed now)
        for lf in log_files:
            target_csvname = LOGS_TO_EXTRACT.get(lf, lf + ".csv")
            target_csvpath = per_pcap_out_dir / target_csvname

            # If CSV exists, load it directly (resume behavior)
            if target_csvpath.exists():
                try:
                    df_existing = pd.read_csv(target_csvpath, dtype=str, low_memory=False)
                    parsed_logs[lf] = df_existing
                    print(f"[SKIP/LOAD] {target_csvpath} (already exists, loaded)")
                    continue
                except Exception as e:
                    # Fall through to re-parse if CSV load fails
                    print(f"[WARN] failed to load existing CSV {target_csvpath}, will reparse .log. Error: {e}")

            # If CSV doesn't exist, parse the .log and save CSV
            logpath = zeek_logs_dir / lf
            try:
                df = parse_zeek_log_to_df(str(logpath))
                if df.empty:
                    print(f"[EMPTY] parsed {logpath} -> empty (skipping write)")
                    parsed_logs[lf] = pd.DataFrame()
                    # write an empty CSV marker to indicate processed, to avoid re-parsing repeatedly
                    try:
                        pd.DataFrame().to_csv(target_csvpath, index=False)
                    except Exception:
                        pass
                    continue
                # add metadata cols
                df['pcap_id'] = pcap_id
                df['orig_class'] = cls
                df['orig_device'] = device
                # save CSV
                df.to_csv(target_csvpath, index=False)
                parsed_logs[lf] = df
                print(f"[PARSED] {logpath} -> {target_csvpath} ({len(df)} rows)")
            except Exception as e:
                print(f"[ERROR] parsing {logpath}: {e}")
                parsed_logs[lf] = pd.DataFrame()

        # update manifest row for this pcap (only once)
        if pcap_id not in existing_pcaps:
            manifest_row = {
                "pcap_id": pcap_id,
                "class": cls,
                "seq": seq,
                "device": device,
                "zeek_log_dir": str(zeek_logs_dir),
                "num_logs": len(log_files)
            }
            # try to fill start/end/duration/num_flows using conn log (if present)
            if "conn.log" in parsed_logs and not parsed_logs["conn.log"].empty:
                try:
                    cdf = parsed_logs["conn.log"]
                    ts_col_candidates = [c for c in ('ts', 'start_time') if c in cdf.columns]
                    if ts_col_candidates:
                        ts_col = ts_col_candidates[0]
                        tsvals = pd.to_numeric(cdf[ts_col], errors='coerce').dropna()
                        if not tsvals.empty:
                            t0 = float(tsvals.min())
                            t1 = float(tsvals.max())
                            manifest_row['start_time_epoch'] = t0
                            manifest_row['end_time_epoch'] = t1
                            manifest_row['duration_s'] = t1 - t0
                    manifest_row['num_flows'] = len(cdf)
                except Exception as e:
                    print("Warning: manifest conn extraction failed:", e)
                    manifest_row['start_time_epoch'] = None
                    manifest_row['end_time_epoch'] = None
                    manifest_row['duration_s'] = None
                    manifest_row['num_flows'] = 0
            else:
                manifest_row['start_time_epoch'] = None
                manifest_row['end_time_epoch'] = None
                manifest_row['duration_s'] = None
                manifest_row['num_flows'] = 0

            pcaps_manifest_rows_new.append(manifest_row)
        else:
            print(f"[MANIFEST] pcap_id {pcap_id} already present in manifest/parquet; skipping manifest add.")

        # If flows for this pcap_id are already in existing flows dataframe, we skip flow assembly (resume-safe).
        if already_in_parquet:
            print(f"[SKIP FLOWS] pcap_id {pcap_id} already in existing all_flows.parquet -> skipping flow enrichment/append.")
            continue

        # Build per-flow enriched rows from conn.csv and other parsed CSVs
        if "conn.log" not in parsed_logs or parsed_logs["conn.log"].empty:
            print(f"[WARN] no conn.log data for {pcap_id}; cannot build flows for this pcap; skipping.")
            continue

        cdf = parsed_logs["conn.log"].copy()
        # ensure uid exists; if missing, create synthetic uid
        if 'uid' not in cdf.columns:
            def mk_uid(r):
                try:
                    return "uid_" + str(abs(hash((str(r.get('id.orig_h','')), str(r.get('id.resp_h','')),
                                                 str(r.get('id.orig_p','')), str(r.get('id.resp_p','')),
                                                 str(r.get('ts',''))))))[:24]
                except Exception:
                    return ""
            cdf['uid'] = cdf.apply(lambda r: mk_uid(r), axis=1)

        # Ensure key columns exist (add None if missing)
        key_cols = ['pcap_id','uid','ts','id.orig_h','id.resp_h','id.orig_p','id.resp_p','proto','service',
                    'duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes','conn_state','history']
        for col in key_cols:
            if col not in cdf.columns:
                cdf[col] = None

        # Append flow dicts
        start_idx = len(all_flows_rows_new)
        for _, row in cdf.iterrows():
            flow = {k: row.get(k, None) for k in key_cols}
            # ip anonymization mapping
            for ipcol in ('id.orig_h','id.resp_h'):
                ip = flow.get(ipcol, None)
                if ip and ip != "-" and pd.notna(ip):
                    if ip not in ip_map:
                        ip_map[ip] = f"dev_{len(ip_map)+1}"
                    flow[ipcol + "_anon"] = ip_map.get(ip)
                    # preserve /24 prefix if IPv4-like
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
            # initialize enrichment counters
            flow.update({
                'dns_q_count': 0,
                'http_count': 0,
                'tls_count': 0,
                'files_count': 0,
                'mqtt_pub_count': 0,
                'notice_count': 0
            })
            all_flows_rows_new.append(flow)

        # map uid -> new-row-index
        uid_to_idx = {}
        for i, uid in enumerate(cdf['uid'].tolist(), start=start_idx):
            if uid:
                uid_to_idx[uid] = i

        # Enrichment from other logs (count rows per uid)
        # DNS
        if "dns.log" in parsed_logs and not parsed_logs["dns.log"].empty:
            try:
                ddf = parsed_logs["dns.log"]
                if 'uid' in ddf.columns:
                    dns_counts = ddf.groupby('uid').size().to_dict()
                    for uid, cnt in dns_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows_new[uid_to_idx[uid]]['dns_q_count'] = int(cnt)
            except Exception as e:
                print("DNS enrichment failed:", e)
        # HTTP
        if "http.log" in parsed_logs and not parsed_logs["http.log"].empty:
            try:
                hdf = parsed_logs["http.log"]
                if 'uid' in hdf.columns:
                    http_counts = hdf.groupby('uid').size().to_dict()
                    for uid, cnt in http_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows_new[uid_to_idx[uid]]['http_count'] = int(cnt)
            except Exception as e:
                print("HTTP enrichment failed:", e)
        # TLS/SSL
        tls_key = None
        if "tls.log" in parsed_logs and not parsed_logs["tls.log"].empty:
            tls_key = "tls.log"
        elif "ssl.log" in parsed_logs and not parsed_logs["ssl.log"].empty:
            tls_key = "ssl.log"
        if tls_key:
            try:
                tdf = parsed_logs[tls_key]
                if 'uid' in tdf.columns:
                    tls_counts = tdf.groupby('uid').size().to_dict()
                    for uid, cnt in tls_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows_new[uid_to_idx[uid]]['tls_count'] = int(cnt)
            except Exception as e:
                print("TLS enrichment failed:", e)
        # FILES
        if "files.log" in parsed_logs and not parsed_logs["files.log"].empty:
            try:
                fdf = parsed_logs["files.log"]
                if 'uid' in fdf.columns:
                    f_counts = fdf.groupby('uid').size().to_dict()
                    for uid, cnt in f_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows_new[uid_to_idx[uid]]['files_count'] = int(cnt)
            except Exception as e:
                print("FILES enrichment failed:", e)
        # MQTT publish
        if "mqtt_publish.log" in parsed_logs and not parsed_logs["mqtt_publish.log"].empty:
            try:
                mdf = parsed_logs["mqtt_publish.log"]
                if 'uid' in mdf.columns:
                    m_counts = mdf.groupby('uid').size().to_dict()
                    for uid, cnt in m_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows_new[uid_to_idx[uid]]['mqtt_pub_count'] = int(cnt)
            except Exception as e:
                print("MQTT enrichment failed:", e)
        # Notices
        if "notice.log" in parsed_logs and not parsed_logs["notice.log"].empty:
            try:
                ndf = parsed_logs["notice.log"]
                if 'uid' in ndf.columns:
                    n_counts = ndf.groupby('uid').size().to_dict()
                    for uid, cnt in n_counts.items():
                        if uid in uid_to_idx:
                            all_flows_rows_new[uid_to_idx[uid]]['notice_count'] = int(cnt)
            except Exception as e:
                print("NOTICE enrichment failed:", e)

        print(f"[NEW FLOWS ADDED] pcap_id {pcap_id}: {len(cdf)} flows queued for append.")

    # end for each zeek_logs dir

    # Merge / write manifests and all_flows.parquet incrementally
    # 1) update pcaps_manifest
    try:
        if pcaps_manifest_rows_new:
            df_new_man = pd.DataFrame(pcaps_manifest_rows_new)
            if not pcaps_manifest_df.empty:
                pcaps_manifest_df = pd.concat([pcaps_manifest_df, df_new_man], ignore_index=True)
                pcaps_manifest_df = pcaps_manifest_df.drop_duplicates(subset=['pcap_id'], keep='first')
            else:
                pcaps_manifest_df = df_new_man
            ensure_dir(os.path.dirname(PCAPS_MANIFEST_PATH))
            pcaps_manifest_df.to_csv(PCAPS_MANIFEST_PATH, index=False)
            print(f"Wrote/updated pcaps manifest: {PCAPS_MANIFEST_PATH}")
        else:
            print("No new manifest rows to append.")
    except Exception as e:
        print("Failed to update pcaps manifest:", e)

    # 2) update ip_map.json
    try:
        ensure_dir(os.path.dirname(IP_MAP_PATH))
        with open(IP_MAP_PATH, "w") as f:
            json.dump(ip_map, f, indent=2)
        print("Wrote/updated ip map:", IP_MAP_PATH)
    except Exception as e:
        print("Failed to write ip_map:", e)

    # 3) assemble flows dataframe and append to existing all_flows.parquet if necessary
    try:
        if all_flows_rows_new:
            new_flows_df = pd.DataFrame(all_flows_rows_new)
            # remove any duplicates using uid+pcap_id against existing flows
            if not existing_flows_df.empty:
                # compute keys and drop collisions
                existing_keys = set((existing_flows_df['pcap_id'].astype(str) + "||" + existing_flows_df['uid'].astype(str)).tolist())
                new_keys = (new_flows_df['pcap_id'].astype(str) + "||" + new_flows_df['uid'].astype(str)).tolist()
                mask = [k not in existing_keys for k in new_keys]
                new_flows_df = new_flows_df[mask]
                merged = pd.concat([existing_flows_df, new_flows_df], ignore_index=True, sort=False)
            else:
                merged = new_flows_df

            ensure_dir(os.path.dirname(ALL_FLOWS_PATH))
            merged.to_parquet(ALL_FLOWS_PATH, index=False)
            print(f"Wrote/updated all_flows.parquet: {ALL_FLOWS_PATH} (total rows: {len(merged)})")
        else:
            print("No new flows to append to all_flows.parquet.")
    except Exception as e:
        print("Failed to write/append all_flows.parquet:", e)

    # 4) regenerate device profiles from Normal class if possible
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
                        'median_bytes_per_flow': float(pd.to_numeric(g['orig_bytes'], errors='coerce').median()) if 'orig_bytes' in g.columns else None,
                        'median_duration_s': float(pd.to_numeric(g['duration'], errors='coerce').median()) if 'duration' in g.columns else None,
                        'common_dst_p24': str(g['id.resp_h_p24'].value_counts().idxmax()) if 'id.resp_h_p24' in g.columns and not g['id.resp_h_p24'].isna().all() else None
                    }
                    profiles.append(profile)
                prof_df = pd.DataFrame(profiles)
                prof_df.to_csv(DEVICE_PROFILES_PATH, index=False)
                print("Wrote device profiles:", DEVICE_PROFILES_PATH)
            else:
                print("No Normal-class flows found - device profiles not generated.")
    except Exception as e:
        print("Device profile generation failed:", e)

    print("\nProcessing finished. Output root:", OUT_DIR)
    print("If the run stopped earlier you can re-run this script; it will skip already-created CSVs and flows present in the parquet.")

if __name__ == "__main__":
    main()
