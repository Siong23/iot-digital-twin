#!/usr/bin/env python3
"""
zeek_to_csv_memory_safe.py

Memory-safe, resume-friendly Zeek -> CSV/Per-pcap-parquet converter.

Behavior:
 - Processes each zeek_logs folder ONE AT A TIME.
 - Skips parsing logs if per-pcap CSV already exists.
 - Builds per-pcap "flows" DataFrame and writes it IMMEDIATELY to a per-pcap parquet:
       processed_dataset/flows/<pcap_id>.parquet
 - Appends manifest rows to manifests/pcaps_manifest.csv (append mode).
 - Updates ip_map.json incrementally.
 - Deletes large variables and calls gc.collect() to free memory between pcaps.

Note: This script does NOT merge all per-pcap flows into a single huge DataFrame (to avoid memory blow).
You can merge later with pyarrow.dataset or on a machine with more RAM.
"""

import os, sys, json, gc
from pathlib import Path
import pandas as pd
import traceback

# ------------- CONFIG -------------
BASE_DIR = "./ZEEK_LOGS"           # Set this to your root folder containing Brute-force/, DDoS/, ...
OUT_ROOT = "./processed_dataset"
PER_PCAP_CSV_DIR = os.path.join(OUT_ROOT, "per_pcap_csvs")   # per-log CSVs
PER_PCAP_FLOWS_DIR = os.path.join(OUT_ROOT, "flows")         # per-pcap parquet flows
MANIFESTS_DIR = os.path.join(OUT_ROOT, "manifests")
PCAPS_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "pcaps_manifest.csv")
IP_MAP_PATH = os.path.join(MANIFESTS_DIR, "ip_map.json")
# Map log file -> csv name
LOGS_TO_EXTRACT = {
    "conn.log":"conn.csv",
    "dns.log":"dns.csv",
    "http.log":"http.csv",
    "ssl.log":"tls.csv",
    "tls.log":"tls.csv",
    "files.log":"files.csv",
    "notice.log":"notice.csv",
    "weird.log":"weird.csv",
    "mqtt_publish.log":"mqtt_publish.csv",
    "mqtt_connect.log":"mqtt_connect.csv",
    "mqtt_subscribe.log":"mqtt_subscribe.csv",
    "mqtt_subcribe.log":"mqtt_subscribe.csv",
    "capture_loss.log":"capture_loss.csv",
    "stats.log":"stats.csv",
    "telemetry.log":"telemetry.csv"
}

# ------------- HELPERS -------------
def ensure_dir(p): 
    Path(p).mkdir(parents=True, exist_ok=True)

def parse_zeek_log_to_df(logpath):
    """
    Parse Zeek log file using #fields header. Return empty DataFrame if header missing.
    """
    cols = None
    rows = []
    try:
        with open(logpath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                if line.startswith("#fields"):
                    # fields are tab-separated after '#fields'
                    parts = line.split("\t")
                    cols = parts[1:]
                    continue
                if line.startswith("#"):
                    continue
                if cols is None:
                    # can't parse rows without header
                    continue
                parts = line.split("\t")
                if len(parts) < len(cols):
                    parts += [""] * (len(cols)-len(parts))
                rows.append(parts[:len(cols)])
    except Exception as e:
        print("Error reading", logpath, ":", e)
        return pd.DataFrame()
    if cols is None:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(rows, columns=cols)
    except Exception:
        df = pd.DataFrame(rows)
        df.columns = cols[:df.shape[1]]
    return df

def infer_pcap_id(zeek_logs_folder):
    p = Path(zeek_logs_folder).resolve()
    parts = p.parts
    if "zeek_logs" in parts:
        i = parts.index("zeek_logs")
        if i >= 3:
            cls = parts[i-3]; seq = parts[i-2]; device = parts[i-1]
            return cls, seq, device, f"{cls}_{seq}_{device}"
    tail = parts[-4:]
    if len(tail) >= 3:
        return tail[-4], tail[-3], tail[-2], f"{tail[-4]}_{tail[-3]}_{tail[-2]}"
    return "unknown","0","unknown","unknown_0_unknown"

def append_manifest_row(row):
    ensure_dir(MANIFESTS_DIR)
    # if file doesn't exist, write header
    if not os.path.exists(PCAPS_MANIFEST_PATH):
        pd.DataFrame([row]).to_csv(PCAPS_MANIFEST_PATH, index=False)
    else:
        pd.DataFrame([row]).to_csv(PCAPS_MANIFEST_PATH, index=False, header=False, mode="a")

def load_ip_map():
    if os.path.exists(IP_MAP_PATH):
        try:
            with open(IP_MAP_PATH,"r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_ip_map(ip_map):
    ensure_dir(MANIFESTS_DIR)
    with open(IP_MAP_PATH,"w") as f:
        json.dump(ip_map, f, indent=2)

# ------------- MAIN -------------
def main():
    base = Path(BASE_DIR)
    if not base.exists():
        print("ERROR: BASE_DIR not found:", BASE_DIR); sys.exit(1)

    ensure_dir(PER_PCAP_CSV_DIR)
    ensure_dir(PER_PCAP_FLOWS_DIR)
    ensure_dir(MANIFESTS_DIR)

    ip_map = load_ip_map()
    ip_counter = max([int(v.split("_")[1]) for v in ip_map.values()]) if ip_map else 0

    # iterate zeek_logs folders one at a time
    for zeek_dir in sorted(base.rglob("zeek_logs")):
        if not zeek_dir.is_dir():
            continue
        cls, seq, device, pcap_id = infer_pcap_id(str(zeek_dir))
        print("\n== Processing:", pcap_id, "==")

        # Make per-pcap CSV dir
        per_pcap_out = Path(PER_PCAP_CSV_DIR) / cls / seq / device
        ensure_dir(per_pcap_out)

        # list .log files
        log_files = sorted([p for p in os.listdir(zeek_dir) if p.endswith(".log")])
        print("Found logs:", log_files)

        # If flows parquet for this pcap already exists, skip heavy processing
        per_pcap_flow_parquet = Path(PER_PCAP_FLOWS_DIR) / f"{pcap_id}.parquet"
        if per_pcap_flow_parquet.exists():
            print("[SKIP] flows parquet exists for", pcap_id, "- skipping creation (resume-safe).")
            # still ensure manifest row present (if not already)
            manifest_row = {"pcap_id": pcap_id, "class": cls, "seq": seq, "device": device, "zeek_log_dir": str(zeek_dir), "num_logs": len(log_files)}
            append_manifest_row(manifest_row)
            continue

        # parse & save individual logs to CSV (skip if CSV exists)
        parsed_frames = {}  # small dict for this pcap only; we will delete it soon
        for lf in log_files:
            target_csv = per_pcap_out / (LOGS_TO_EXTRACT.get(lf, lf+".csv"))
            if target_csv.exists():
                try:
                    # Option: don't load existing CSV into memory unless needed (we won't unless enriching)
                    df_existing = None
                    parsed_frames[lf] = None  # mark it exists and skip parsing unless we need it later
                    print(f"[SKIP CSV] {target_csv} exists")
                    continue
                except Exception:
                    pass
            # parse log
            try:
                df = parse_zeek_log_to_df(str(zeek_dir / lf))
                # save CSV even if empty (marker)
                try:
                    df.to_csv(target_csv, index=False)
                except Exception:
                    pass
                parsed_frames[lf] = df
                print(f"[PARSED] {lf} -> {target_csv} ({len(df)} rows)")
            except Exception as e:
                print("Failed to parse", lf, ":", e)
                parsed_frames[lf] = None

        # Build per-pcap flows directly and write to per-pcap parquet immediately
        # Use conn.log if present (either parsed_frames["conn.log"] or the CSV if it existed)
        try:
            # load conn.csv if exists on disk and parsed_frames[conn.log] is None
            conn_csv_path = per_pcap_out / "conn.csv"
            if parsed_frames.get("conn.log") is None and conn_csv_path.exists():
                try:
                    cdf = pd.read_csv(conn_csv_path, dtype=str, low_memory=False)
                except Exception:
                    cdf = parse_zeek_log_to_df(str(zeek_dir / "conn.log"))
            else:
                cdf = parsed_frames.get("conn.log", pd.DataFrame())

            if cdf is None:
                cdf = pd.DataFrame()
            if cdf.empty:
                print("[WARN] conn.log missing or empty for", pcap_id, "- skipping flow creation.")
                # Still write manifest row and continue.
                manifest_row = {"pcap_id": pcap_id, "class": cls, "seq": seq, "device": device, "zeek_log_dir": str(zeek_dir), "num_logs": len(log_files)}
                append_manifest_row(manifest_row)
                # free and continue
                parsed_frames.clear(); del parsed_frames; gc.collect()
                continue

            # ensure uid column exists
            if 'uid' not in cdf.columns:
                # generate synthetic uid (best-effort)
                def make_uid_row(r):
                    try:
                        key = f"{r.get('id.orig_h','')}_{r.get('id.resp_h','')}_{r.get('id.orig_p','')}_{r.get('id.resp_p','')}_{r.get('ts','')}"
                        return "uid_" + str(abs(hash(key)))[:24]
                    except Exception:
                        return ""
                cdf['uid'] = cdf.apply(lambda r: make_uid_row(r), axis=1)

            # select & ensure key columns exist
            keep_cols = ['uid','ts','id.orig_h','id.resp_h','id.orig_p','id.resp_p','proto','service','duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes','conn_state','history']
            for col in keep_cols:
                if col not in cdf.columns:
                    cdf[col] = None

            # build flows_df minimal
            flows_df = cdf[keep_cols].copy()
            # add metadata columns and default enrichment counts
            flows_df['pcap_id'] = pcap_id
            flows_df['class'] = cls
            flows_df['device'] = device
            flows_df['dns_q_count'] = 0
            flows_df['http_count'] = 0
            flows_df['tls_count'] = 0
            flows_df['files_count'] = 0
            flows_df['mqtt_pub_count'] = 0
            flows_df['notice_count'] = 0

            # anonymize IPs and update ip_map
            def anon_ip(ip):
                nonlocal ip_counter
                if pd.isna(ip) or ip in ("", "-"):
                    return None, None
                if ip not in ip_map:
                    ip_counter += 1
                    ip_map[ip] = f"dev_{ip_counter}"
                anon = ip_map.get(ip)
                # p24
                p24 = None
                try:
                    parts = str(ip).split(".")
                    if len(parts) == 4:
                        p24 = ".".join(parts[:3]) + ".0/24"
                except Exception:
                    p24 = None
                return anon, p24

            flows_df['id.orig_h_anon'] = None
            flows_df['id.orig_h_p24'] = None
            flows_df['id.resp_h_anon'] = None
            flows_df['id.resp_h_p24'] = None

            # iterate rows in chunks to avoid building huge intermediate lists
            for idx, row in flows_df.iterrows():
                oip = row['id.orig_h']
                rip = row['id.resp_h']
                anon_o, p24_o = anon_ip(oip)
                anon_r, p24_r = anon_ip(rip)
                flows_df.at[idx, 'id.orig_h_anon'] = anon_o
                flows_df.at[idx, 'id.orig_h_p24'] = p24_o
                flows_df.at[idx, 'id.resp_h_anon'] = anon_r
                flows_df.at[idx, 'id.resp_h_p24'] = p24_r

            # ENRICHMENT: count rows in other logs by uid if we have the other parsed frames
            # To minimize memory, we try to load CSVs from disk if parsed_frames has None
            def get_df(lname):
                # lname is e.g. "dns.log" -> csv name per_pcap_out/dns.csv
                csvname = LOGS_TO_EXTRACT.get(lname, lname + ".csv")
                csvpath = per_pcap_out / csvname
                if csvpath.exists():
                    try:
                        return pd.read_csv(csvpath, dtype=str, low_memory=False)
                    except Exception:
                        try:
                            return parse_zeek_log_to_df(str(zeek_dir / lname))
                        except Exception:
                            return pd.DataFrame()
                else:
                    # maybe parsed_frames has it in memory
                    df = parsed_frames.get(lname)
                    return df if (df is not None) else pd.DataFrame()

            # dns counts
            ddf = get_df("dns.log")
            if ddf is not None and not ddf.empty and 'uid' in ddf.columns:
                dns_counts = ddf.groupby('uid').size()
                # map counts back by uid
                flows_df['dns_q_count'] = flows_df['uid'].map(dns_counts).fillna(0).astype(int)

            # http counts
            hdf = get_df("http.log")
            if hdf is not None and not hdf.empty and 'uid' in hdf.columns:
                http_counts = hdf.groupby('uid').size()
                flows_df['http_count'] = flows_df['uid'].map(http_counts).fillna(0).astype(int)

            # tls/ssl counts
            tdf = get_df("tls.log")
            if (tdf is None or tdf.empty) :
                tdf = get_df("ssl.log")
            if tdf is not None and not tdf.empty and 'uid' in tdf.columns:
                tls_counts = tdf.groupby('uid').size()
                flows_df['tls_count'] = flows_df['uid'].map(tls_counts).fillna(0).astype(int)

            # files counts
            fdf = get_df("files.log")
            if fdf is not None and not fdf.empty and 'uid' in fdf.columns:
                f_counts = fdf.groupby('uid').size()
                flows_df['files_count'] = flows_df['uid'].map(f_counts).fillna(0).astype(int)

            # mqtt publish counts
            mdf = get_df("mqtt_publish.log")
            if mdf is not None and not mdf.empty and 'uid' in mdf.columns:
                m_counts = mdf.groupby('uid').size()
                flows_df['mqtt_pub_count'] = flows_df['uid'].map(m_counts).fillna(0).astype(int)

            # notices
            ndf = get_df("notice.log")
            if ndf is not None and not ndf.empty and 'uid' in ndf.columns:
                n_counts = ndf.groupby('uid').size()
                flows_df['notice_count'] = flows_df['uid'].map(n_counts).fillna(0).astype(int)

            # FINAL: write flows_df to per-pcap parquet IMMEDIATELY
            ensure_dir(PER_PCAP_FLOWS_DIR)
            out_parquet = Path(PER_PCAP_FLOWS_DIR) / f"{pcap_id}.parquet"
            try:
                # Use PyArrow engine via pandas
                flows_df.to_parquet(out_parquet, index=False)
                print("[WROTE] per-pcap flows parquet:", out_parquet, "rows:", len(flows_df))
            except Exception as e:
                print("Failed to write per-pcap parquet:", e)
                # fallback: write csv
                csv_fallback = out_parquet.with_suffix(".csv")
                flows_df.to_csv(csv_fallback, index=False)
                print("[WROTE] per-pcap flows csv fallback:", csv_fallback)

            # append manifest row so progress is recorded on disk
            manifest_row = {
                "pcap_id": pcap_id,
                "class": cls,
                "seq": seq,
                "device": device,
                "zeek_log_dir": str(zeek_dir),
                "num_logs": len(log_files),
                "num_flows": len(flows_df)
            }
            append_manifest_row(manifest_row)

            # cleanup large objects
            del cdf
            del flows_df
            # free parsed frames for this pcap
            parsed_frames.clear()
            del parsed_frames
            # persist ip_map incrementally
            save_ip_map(ip_map)
            # force garbage collection
            gc.collect()

        except Exception as e:
            print("ERROR processing pcap:", pcap_id, "exception:", e)
            traceback.print_exc()
            # attempt to free and continue
            try:
                parsed_frames.clear()
                del parsed_frames
            except Exception:
                pass
            gc.collect()
            continue

    # End loop over zeek_logs folders
    print("\nAll done. Per-pcap flows are in:", PER_PCAP_FLOWS_DIR)
    print("Manifests in:", PCAPS_MANIFEST_PATH)
    print("IP mapping in:", IP_MAP_PATH)
    print("To produce a single merged dataset later, you can combine per-pcap parquet files using pyarrow.dataset or pandas on a machine with more RAM.")

if __name__ == "__main__":
    main()
