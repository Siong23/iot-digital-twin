#!/usr/bin/env python3
"""
zeek_extract_and_merge.py

- Unzips /mnt/data/ZEEK_LOGS.zip if present into /mnt/data/zeek_logs_unpacked
  (adjust ZIP_PATH / UNPACK_DIR variables if running locally).
- Walks the unpacked Zeek logs tree and parses conn.log (backbone).
- Produces per-pcap flows CSV under OUT_DIR/<Attack>/<Run>/<Device>/flows_<pcap_id>.csv
- Copies other relevant logs (dns/http/tls/files/notice/mqtt*) as CSVs into same per-pcap folders.
- Streams all per-pcap flow CSVs into OUT_DIR/all_flows_streamed.csv and writes summary_by_attack.csv.

Usage:
    python3 zeek_extract_and_merge.py
Change constants at top if you keep files elsewhere.
"""
import os, zipfile, shutil, csv, json
from pathlib import Path
import pandas as pd
import numpy as np
import sys

# === CONFIGURE THESE PATHS ===
ZIP_PATH = "/mnt/data/ZEEK_LOGS.zip"                 # set to None if not using zip
UNPACK_DIR = "/mnt/data/zeek_logs_unpacked"
OUT_DIR = "/mnt/data/csv_output"
KNOWN_CLASSES = ["Brute-force","DDoS","MQTT","Normal","RTSP","Scanning","Brute_force","Bruteforce"]

# === helper functions ===
def unzip_if_exists(zip_path=ZIP_PATH, dest=UNPACK_DIR):
    if zip_path and os.path.exists(zip_path):
        print(f"Unzipping {zip_path} -> {dest} ...")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(dest)
        print("Unzip complete.")
        return dest
    if os.path.exists(dest) and any(os.scandir(dest)):
        print(f"Using existing unpack dir: {dest}")
        return dest
    print("No zip found and unpack dir missing:", zip_path, dest)
    return None

def find_attack_run_device(path_parts):
    # path_parts: list/tuple of path components relative to unpack dir
    for i, p in enumerate(path_parts):
        if p in KNOWN_CLASSES:
            attack = p
            run = path_parts[i+1] if i+1 < len(path_parts) else "unknown"
            device = path_parts[i+2] if i+2 < len(path_parts) else "unknown"
            return attack, run, device
    # fallback: look for numeric 'run'
    for i,p in enumerate(path_parts):
        if p.isdigit():
            attack = path_parts[i-1] if i-1 >=0 else "unknown"
            run = p
            device = path_parts[i+1] if i+1 < len(path_parts) else "unknown"
            return attack, run, device
    # fallback to last three components
    if len(path_parts) >= 3:
        return path_parts[-3], path_parts[-2], path_parts[-1]
    if len(path_parts) == 2:
        return path_parts[-2], path_parts[-1], "unknown"
    if len(path_parts) == 1:
        return path_parts[-1], "unknown", "unknown"
    return "unknown","unknown","unknown"

def parse_zeek_log_to_df(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        # Zeek logs are tab-separated and comment lines start with '#'
        df = pd.read_table(path, comment="#", low_memory=False)
        return df
    except Exception:
        # fallback manual parse in case of weird formatting
        cols=[]
        rows=[]
        with open(path, 'r', errors='replace') as fh:
            for line in fh:
                line=line.rstrip("\n")
                if line.startswith("#fields"):
                    parts=line.split(None,1)
                    if len(parts)>1:
                        cols = parts[1].split("\t") if "\t" in parts[1] else parts[1].split()
                    continue
                if line.startswith("#"): 
                    continue
                if not cols:
                    continue
                vals=line.split("\t")
                if len(vals) < len(cols):
                    vals += [""]*(len(cols)-len(vals))
                rows.append(vals)
        if not rows:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame(rows, columns=cols)

# === main processing ===
def main():
    base = unzip_if_exists()
    if base is None:
        # try using a local folder named "ZEEK_LOGS" next to script
        local = os.path.join(os.getcwd(), "ZEEK_LOGS")
        if os.path.exists(local) and any(os.scandir(local)):
            base = local
            print("Using local ZEEK_LOGS folder:", local)
        else:
            print("No Zeek logs found. Put ZEEK_LOGS.zip at /mnt/data/ or create ZEEK_LOGS folder. Exiting.")
            sys.exit(1)

    # prepare output
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    flow_csv_paths = []

    # Walk the unpacked tree and focus on folders that contain conn.log
    for root, dirs, files in os.walk(base):
        if "conn.log" not in files:
            continue
        rel = os.path.relpath(root, base)
        parts = rel.split(os.sep) if rel not in (".","..") else []
        attack, run_id, device = find_attack_run_device(parts)
        pcap_id = f"{attack}_{run_id}_{device}"
        out_folder = os.path.join(OUT_DIR, attack, run_id, device)
        os.makedirs(out_folder, exist_ok=True)

        # parse conn.log
        conn_path = os.path.join(root, "conn.log")
        conn_df = parse_zeek_log_to_df(conn_path)
        if conn_df.empty:
            print("Empty conn.log for", root)
            continue

        # Ensure expected columns exist
        expected = ["ts","uid","id.orig_h","id.resp_h","id.orig_p","id.resp_p","proto","service","duration","orig_pkts","resp_pkts","orig_bytes","resp_bytes","conn_state","history"]
        for c in expected:
            if c not in conn_df.columns:
                conn_df[c] = ""

        # Select/rename cols for flows
        flows = conn_df[["ts","uid","id.orig_h","id.resp_h","id.orig_p","id.resp_p","proto","service","duration","orig_pkts","resp_pkts","orig_bytes","resp_bytes","conn_state","history"]].copy()
        flows = flows.rename(columns={
            "ts":"ts_start",
            "uid":"flow_uid",
            "id.orig_h":"src_ip",
            "id.resp_h":"dst_ip",
            "id.orig_p":"src_port",
            "id.resp_p":"dst_port",
            "duration":"duration_s"
        })
        flows["pcap_id"] = pcap_id
        flows["attack_type"] = attack
        flows["run_id"] = run_id
        flows["device"] = device

        # numeric cast
        for col in ["src_port","dst_port","orig_pkts","resp_pkts","orig_bytes","resp_bytes","duration_s"]:
            if col in flows.columns:
                flows[col] = pd.to_numeric(flows[col], errors='coerce').fillna(0).astype(np.int64)

        flows["total_bytes"] = flows["orig_bytes"].astype(np.int64) + flows["resp_bytes"].astype(np.int64)
        flows["total_pkts"] = flows["orig_pkts"].astype(np.int64) + flows["resp_pkts"].astype(np.int64)

        # Enrich from other logs in the same folder (counts by uid)
        # DNS
        dns_df = parse_zeek_log_to_df(os.path.join(root, "dns.log"))
        if not dns_df.empty and "uid" in dns_df.columns:
            dns_counts = dns_df["uid"].value_counts().to_dict()
            flows["dns_count"] = flows["flow_uid"].map(lambda u: dns_counts.get(u,0))
        else:
            flows["dns_count"] = 0

        # HTTP
        http_df = parse_zeek_log_to_df(os.path.join(root, "http.log"))
        if not http_df.empty and "uid" in http_df.columns:
            http_counts = http_df["uid"].value_counts().to_dict()
            hosts = http_df.groupby("uid")["host"].agg(lambda s: s.dropna().iloc[0] if s.dropna().shape[0]>0 else "")
            flows["http_count"] = flows["flow_uid"].map(lambda u: http_counts.get(u,0))
            flows["http_host"] = flows["flow_uid"].map(lambda u: hosts.get(u,"") if u in hosts.index else "")
        else:
            flows["http_count"] = 0
            flows["http_host"] = ""

        # TLS/SSL
        tls_df = pd.DataFrame()
        if os.path.exists(os.path.join(root, "tls.log")):
            tls_df = parse_zeek_log_to_df(os.path.join(root, "tls.log"))
        elif os.path.exists(os.path.join(root, "ssl.log")):
            tls_df = parse_zeek_log_to_df(os.path.join(root, "ssl.log"))
        if not tls_df.empty and "uid" in tls_df.columns:
            tls_counts = tls_df["uid"].value_counts().to_dict()
            server_name = tls_df.groupby("uid")["server_name"].agg(lambda s: s.dropna().iloc[0] if s.dropna().shape[0]>0 else "")
            ja3_map = tls_df.groupby("uid")["ja3"].agg(lambda s: s.dropna().iloc[0] if s.dropna().shape[0]>0 else "")
            flows["tls_count"] = flows["flow_uid"].map(lambda u: int(tls_counts.get(u,0)))
            flows["tls_server_name"] = flows["flow_uid"].map(lambda u: server_name.get(u,"") if u in server_name.index else "")
            flows["tls_ja3"] = flows["flow_uid"].map(lambda u: ja3_map.get(u,"") if u in ja3_map.index else "")
        else:
            flows["tls_count"] = 0
            flows["tls_server_name"] = ""
            flows["tls_ja3"] = ""

        # files.log
        files_df = parse_zeek_log_to_df(os.path.join(root, "files.log"))
        if not files_df.empty and "uid" in files_df.columns:
            file_counts = files_df["uid"].value_counts().to_dict()
            flows["file_count"] = flows["flow_uid"].map(lambda u: file_counts.get(u,0))
        else:
            flows["file_count"] = 0

        # notice/weird
        notice_df = parse_zeek_log_to_df(os.path.join(root, "notice.log"))
        if not notice_df.empty and "uid" in notice_df.columns:
            notice_counts = notice_df["uid"].value_counts().to_dict()
            flows["notice_count"] = flows["flow_uid"].map(lambda u: notice_counts.get(u,0))
        else:
            flows["notice_count"] = 0

        # mqtt logs if present
        mqtt_pub = parse_zeek_log_to_df(os.path.join(root, "mqtt_publish.log"))
        if not mqtt_pub.empty and "uid" in mqtt_pub.columns:
            mqtt_counts = mqtt_pub["uid"].value_counts().to_dict()
            flows["mqtt_publish_count"] = flows["flow_uid"].map(lambda u: mqtt_counts.get(u,0))
        else:
            flows["mqtt_publish_count"] = 0

        mqtt_conn = parse_zeek_log_to_df(os.path.join(root, "mqtt_connect.log"))
        flows["mqtt_connect_count"] = 0
        if not mqtt_conn.empty and "uid" in mqtt_conn.columns:
            conn_counts = mqtt_conn["uid"].value_counts().to_dict()
            flows["mqtt_connect_count"] = flows["flow_uid"].map(lambda u: conn_counts.get(u,0))

        mqtt_sub = parse_zeek_log_to_df(os.path.join(root, "mqtt_subcribe.log"))
        if not mqtt_sub.empty and "uid" in mqtt_sub.columns:
            sub_counts = mqtt_sub["uid"].value_counts().to_dict()
            flows["mqtt_sub_count"] = flows["flow_uid"].map(lambda u: sub_counts.get(u,0))
        else:
            flows["mqtt_sub_count"] = 0

        # anonymize IPs (per-pcap mapping)
        unique_ips = pd.concat([flows["src_ip"], flows["dst_ip"]]).dropna().unique().tolist()
        ip_map = {ip: f"ip_{i+1}" for i,ip in enumerate(unique_ips)}
        flows["src_ip_anon"] = flows["src_ip"].map(lambda x: ip_map.get(x,"") if x!="" else "")
        flows["dst_ip_anon"] = flows["dst_ip"].map(lambda x: ip_map.get(x,"") if x!="" else "")

        # save per-pcap flows CSV
        out_csv = os.path.join(out_folder, f"flows_{pcap_id}.csv")
        flows.to_csv(out_csv, index=False)
        flow_csv_paths.append(out_csv)
        # save ip_map
        ipmap_csv = os.path.join(out_folder, "ip_map.csv")
        pd.DataFrame([{"original_ip":k,"anon":v} for k,v in ip_map.items()]).to_csv(ipmap_csv, index=False)

        # copy other logs as CSVs for reference
        for logname in ["dns.log","http.log","tls.log","ssl.log","files.log","notice.log","weird.log","mqtt_publish.log","mqtt_connect.log","mqtt_subcribe.log"]:
            src = os.path.join(root, logname)
            if os.path.exists(src):
                try:
                    df_src = parse_zeek_log_to_df(src)
                    df_src.to_csv(os.path.join(out_folder, logname.replace(".log",".csv")), index=False)
                except Exception as e:
                    print("Could not save", src, e)

        print(f"Wrote flows for {pcap_id} -> {out_csv} ({len(flows)} rows)")

    # merge via streaming to avoid memory issues
    if not flow_csv_paths:
        print("No flows produced. Exiting.")
        sys.exit(0)

    merged_path = os.path.join(OUT_DIR, "all_flows_streamed.csv")
    # determine header from first file
    first = flow_csv_paths[0]
    with open(first, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
    with open(merged_path, "w", newline='') as out_f:
        writer = csv.writer(out_f)
        writer.writerow(header)
        for fp in flow_csv_paths:
            with open(fp, newline='') as inf:
                r = csv.reader(inf)
                h = next(r)
                if h != header:
                    # use DictReader to align fields
                    inf.seek(0)
                    dr = csv.DictReader(inf)
                    for row in dr:
                        writer.writerow([row.get(col,"") for col in header])
                else:
                    for row in r:
                        writer.writerow(row)
    print("Merged flows to:", merged_path)

    # summary by attack
    master = pd.read_csv(merged_path, usecols=["attack_type","flow_uid"])
    summary = master.groupby("attack_type").agg({"flow_uid":"count"}).rename(columns={"flow_uid":"num_flows"}).reset_index()
    summary.to_csv(os.path.join(OUT_DIR, "summary_by_attack.csv"), index=False)
    print("Wrote summary_by_attack.csv")

if __name__ == "__main__":
    main()
