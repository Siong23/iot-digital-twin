#!/usr/bin/env python3
"""
zeek_logs_to_csv.py

Usage:
    python zeek_logs_to_csv.py --zeek-root /path/to/zeek_root --out /path/to/output_dir \
        [--pcaps-manifest /path/to/pcaps_manifest.csv] [--do-packet-aggregates]

What it does:
- Walks the zeek_root directory tree
- For each folder that contains Zeek .log files, parses Zeek logs robustly and writes CSVs
  preserving the folder structure under the output dir.
- Produces a per-flow CSV (flows_<pcap_id>.csv) for every folder that has conn.log, augmented
  with counts from dns/http/tls/files/notice/mqtt logs when those exist.
- Optionally, if you supply a pcaps_manifest.csv (with columns pcap_id,pcap_path) and have tshark,
  it will produce per-pcap packet CSV and compute packet-aggregates per 5-tuple (best-effort).
Notes:
- This script *does not* keep raw payloads. Use it for defensive dataset creation only.
- Zeek logs typically use headers starting with '#fields' and '#separator' — this parser respects that.
"""

import argparse
import os
import csv
import sys
import io
import re
from pathlib import Path
from collections import defaultdict
import subprocess
import math

try:
    import pandas as pd
    import numpy as np
except Exception as e:
    print("This script requires pandas and numpy. Install them with: pip install pandas numpy")
    raise

def decode_zeek_separator(s):
    """
    Zeek emits a #separator line like: #separator \x09
    Convert the \x## escapes to the actual character.
    """
    # s expected like: r"\x09" or "\\x09" sometimes; normalize
    # Remove leading/trailing whitespace
    s = s.strip()
    # Replace common escape tokens
    # handle sequences like \x09
    def repl(m):
        hexpart = m.group(1)
        return chr(int(hexpart, 16))
    return re.sub(r'\\x([0-9A-Fa-f]{2})', repl, s)

def parse_zeek_log(path):
    """
    Parse a Zeek log file into a pandas DataFrame.
    Respects #fields and #separator and skips comment lines starting with '#'.
    Returns (df, header_fields)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    sep = '\t'  # default
    fields = None
    types = None
    rows = []
    # Some Zeek logs contain header lines like:
    # #separator \x09
    # #set_separator\t,
    # #empty_field\t(empty)
    # #unset_field\t-
    # #path\tconn
    # #open\t2025-09-...
    # #fields\tts\tuid\tid.orig_h\t...
    with open(path, 'rb') as f:
        # Read bytes and decode line by line, to respect possible non-utf8 bytes
        for raw in f:
            try:
                line = raw.decode('utf-8', errors='replace').rstrip('\n\r')
            except:
                line = raw.decode('latin1', errors='replace').rstrip('\n\r')
            if not line:
                continue
            if line.startswith('#'):
                # header meta
                if line.startswith('#separator'):
                    # remainder after '#separator ' is the escape sequence
                    parts = line.split(None, 1)
                    if len(parts) > 1:
                        sep = decode_zeek_separator(parts[1])
                    else:
                        sep = '\t'
                elif line.startswith('#fields'):
                    # fields are space-separated tokens after '#fields'
                    # Zeek uses tab-separated logs but lists fields separated by tabs or spaces
                    fields = line.split(None, 1)[1].split()
                elif line.startswith('#types'):
                    types = line.split(None, 1)[1].split()
                continue
            # data line
            # If we don't know fields yet, fallback to splitting by tab and using generic column names
            if fields is None:
                parts = line.split('\t')
                # create temporary fields
                if not rows:
                    fields = [f'c{i}' for i in range(len(parts))]
                rows.append(parts)
            else:
                parts = line.split(sep)
                # Zeek uses '-' for unset fields; we will keep as empty string
                rows.append([None if p == '-' else p for p in parts])
    if fields is None:
        # Nothing to parse
        return pd.DataFrame(), []
    # Ensure rows are padded to fields length
    maxcols = max(len(r) for r in rows) if rows else 0
    if maxcols > len(fields):
        # extend fields
        fields = fields + [f'extra{i}' for i in range(maxcols - len(fields))]
    norm_rows = [r + [None]*(len(fields)-len(r)) if len(r) < len(fields) else r[:len(fields)] for r in rows]
    df = pd.DataFrame(norm_rows, columns=fields)
    # Replace '' with NaN
    df.replace({None: pd.NA, '': pd.NA}, inplace=True)
    return df, fields

def safe_mkdir(p):
    Path(p).mkdir(parents=True, exist_ok=True)

def write_csv(df, outpath):
    safe_mkdir(Path(outpath).parent)
    df.to_csv(outpath, index=False)

def process_folder(folder_path, out_root, pcap_id=None):
    """
    For a single zeek_logs folder, parse important logs and write CSVs.
    Returns a dict with paths to written CSVs and a flows DataFrame (or None if conn.log absent).
    """
    folder = Path(folder_path)
    rel = folder.relative_to(folder.anchor) if folder.is_absolute() else Path(folder)
    # We'll create output structure under out_root/mirrored relative path
    out_base = Path(out_root) / folder.relative_to(folder.parent.parent) if (folder.parent and folder.parent.parent) else Path(out_root) / folder.name
    # fallback: simpler mirror
    out_base = Path(out_root) / folder.name if not out_base.exists() else out_base
    safe_mkdir(out_base)
    results = {}
    # Known logs to parse if present
    logs = {p.name: p for p in folder.glob('*.log')}
    # parse each relevant log and emit CSV copy
    parsed = {}
    for name in ['conn.log','dns.log','http.log','tls.log','ssl.log','files.log','notice.log','weird.log',
                 'mqtt_connect.log','mqtt_publish.log','mqtt_subcribe.log','mqtt_subscribe.log','dhcp.log','arp.log','x509.log']:
        if name in logs:
            try:
                df, fields = parse_zeek_log(logs[name])
            except Exception as e:
                print(f"Failed to parse {logs[name]}: {e}", file=sys.stderr)
                continue
            # write CSV
            outp = out_base / f"{name}.csv"
            try:
                write_csv(df, outp)
            except Exception as e:
                print(f"Failed to write {outp}: {e}", file=sys.stderr)
            parsed[name] = (df, outp)
            results[name] = str(outp)
    # Build flows table if conn.log exists
    flows_df = None
    if 'conn.log' in parsed:
        conn_df = parsed['conn.log'][0].copy()
        # ensure common columns exist; Zeek fields might differ by versions
        # Typical fields: ts, uid, id.orig_h, id.resp_h, id.orig_p, id.resp_p, proto, service, duration, orig_pkts, resp_pkts, orig_bytes, resp_bytes, conn_state, history
        # Normalize columns by mapping common aliases
        col_map = {}
        for c in conn_df.columns:
            lower = c.lower()
            if lower in ('ts','timestamp'):
                col_map[c] = 'ts'
            elif lower in ('uid',):
                col_map[c] = 'uid'
            elif lower in ('id.orig_h','orig_h','src_ip'):
                col_map[c] = 'id.orig_h'
            elif lower in ('id.resp_h','resp_h','dst_ip'):
                col_map[c] = 'id.resp_h'
            elif lower in ('id.orig_p','orig_p','src_port'):
                col_map[c] = 'id.orig_p'
            elif lower in ('id.resp_p','resp_p','dst_port'):
                col_map[c] = 'id.resp_p'
            elif lower in ('proto',):
                col_map[c] = 'proto'
            elif lower in ('service',):
                col_map[c] = 'service'
            elif lower in ('duration',):
                col_map[c] = 'duration'
            elif lower in ('orig_pkts','orig_pkts'):
                col_map[c] = 'orig_pkts'
            elif lower in ('resp_pkts','resp_pkts'):
                col_map[c] = 'resp_pkts'
            elif lower in ('orig_bytes','orig_bytes'):
                col_map[c] = 'orig_bytes'
            elif lower in ('resp_bytes','resp_bytes'):
                col_map[c] = 'resp_bytes'
            elif lower in ('conn_state','connection_state'):
                col_map[c] = 'conn_state'
            elif lower in ('history',):
                col_map[c] = 'history'
        conn_df.rename(columns=col_map, inplace=True)
        # Keep at least uid and timestamps
        needed = ['uid','ts','id.orig_h','id.resp_h','id.orig_p','id.resp_p','proto','service','duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes','conn_state','history']
        available = [c for c in needed if c in conn_df.columns]
        flows_df = conn_df[available].copy()
        # add pcap_id if provided
        if pcap_id:
            flows_df.insert(0, 'pcap_id', pcap_id)
        else:
            # derive pcap_id from folder name (best-effort)
            pcap_guess = folder.parts[-3:] if len(folder.parts)>=3 else folder.name
            flows_df.insert(0,'pcap_id', "_".join(map(str,pcap_guess)))
        # Convert numeric-like columns
        for numeric_col in ['id.orig_p','id.resp_p','duration','orig_pkts','resp_pkts','orig_bytes','resp_bytes']:
            if numeric_col in flows_df.columns:
                flows_df[numeric_col] = pd.to_numeric(flows_df[numeric_col], errors='coerce')
        # Add counts from other logs by uid mapping (where uid exists)
        # If uid is not present, we will try to aggregate by matching src/dst/ports where possible
        uid_col = 'uid' if 'uid' in flows_df.columns else None
        # helper to count events per uid
        def count_by_uid(logdf):
            if logdf is None or 'uid' not in logdf.columns:
                return {}
            s = logdf['uid'].value_counts(dropna=True)
            return s.to_dict()
        # dns count
        dns_counts = {}
        if 'dns.log' in parsed:
            dns_counts = count_by_uid(parsed['dns.log'][0])
        http_counts = {}
        if 'http.log' in parsed:
            http_counts = count_by_uid(parsed['http.log'][0])
        files_counts = {}
        if 'files.log' in parsed:
            files_counts = count_by_uid(parsed['files.log'][0])
        notice_counts = {}
        if 'notice.log' in parsed:
            notice_counts = count_by_uid(parsed['notice.log'][0])
        weird_counts = {}
        if 'weird.log' in parsed:
            weird_counts = count_by_uid(parsed['weird.log'][0])
        mqtt_pub_counts = {}
        if 'mqtt_publish.log' in parsed:
            mqtt_pub_counts = count_by_uid(parsed['mqtt_publish.log'][0])
        # apply counts
        def map_counts(row, counts):
            if 'uid' in row and pd.notna(row['uid']):
                return counts.get(row['uid'], 0)
            else:
                return 0
        flows_df['dns_count'] = flows_df.apply(lambda r: map_counts(r, dns_counts), axis=1)
        flows_df['http_count'] = flows_df.apply(lambda r: map_counts(r, http_counts), axis=1)
        flows_df['file_count'] = flows_df.apply(lambda r: map_counts(r, files_counts), axis=1)
        flows_df['notice_count'] = flows_df.apply(lambda r: map_counts(r, notice_counts), axis=1)
        flows_df['weird_count'] = flows_df.apply(lambda r: map_counts(r, weird_counts), axis=1)
        flows_df['mqtt_publish_count'] = flows_df.apply(lambda r: map_counts(r, mqtt_pub_counts), axis=1)
        # fill NaN with zeros on count columns
        for c in ['dns_count','http_count','file_count','notice_count','weird_count','mqtt_publish_count']:
            flows_df[c] = flows_df[c].fillna(0).astype(int)
        # save per-flow CSV
        outp_flows = out_base / f"flows_{flows_df['pcap_id'].iat[0]}.csv"
        write_csv(flows_df, outp_flows)
        results['flows_csv'] = str(outp_flows)
    else:
        print(f"Warning: no conn.log in {folder}. Can't produce flow CSV.", file=sys.stderr)
    return results, flows_df

def compute_packet_aggregates_from_pcap(pcap_path, out_dir, group_on_5tuple=True):
    """
    Optional step: uses tshark to extract packet records and then computes per-5-tuple aggregates.
    Requires tshark to be installed and accessible in PATH.
    This is best-effort and groups by src/dst/ip/ports/proto and time buckets.
    """
    out_dir = Path(out_dir)
    safe_mkdir(out_dir)
    packets_csv = out_dir / f"packets_{Path(pcap_path).stem}.csv"
    # tshark command to extract time, src, dst, srcport, dstport, proto, length
    tshark_cmd = [
        "tshark", "-r", str(pcap_path),
        "-T", "fields",
        "-e", "frame.time_epoch",
        "-e", "ip.src",
        "-e", "ip.dst",
        "-e", "tcp.srcport",
        "-e", "tcp.dstport",
        "-e", "udp.srcport",
        "-e", "udp.dstport",
        "-e", "frame.len",
        "-E", "header=y", "-E", "separator=,", "-E", "quote=d"
    ]
    try:
        print("Running tshark (this can take a while):", " ".join(tshark_cmd))
        with subprocess.Popen(tshark_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                print("tshark error:", stderr[:1000], file=sys.stderr)
                return None
            # write packets CSV
            with open(packets_csv, "w") as f:
                f.write(stdout)
    except FileNotFoundError:
        print("tshark not found - skipping packet extraction. Install tshark to enable packet-aggregate generation.", file=sys.stderr)
        return None
    # load into pandas and normalize ports
    pkdf = pd.read_csv(packets_csv)
    # unify srcport/dstport (choose tcp.* if exist else udp.*)
    def unify_port(row, p1, p2):
        v = row.get(p1)
        if pd.notna(v):
            return v
        return row.get(p2)
    pkdf['src_port'] = pkdf.apply(lambda r: unify_port(r, 'tcp.srcport','udp.srcport'), axis=1)
    pkdf['dst_port'] = pkdf.apply(lambda r: unify_port(r, 'tcp.dstport','udp.dstport'), axis=1)
    pkdf['proto'] = pkdf.apply(lambda r: ('tcp' if pd.notna(r.get('tcp.srcport')) or pd.notna(r.get('tcp.dstport')) else ('udp' if pd.notna(r.get('udp.srcport')) or pd.notna(r.get('udp.dstport')) else 'ip')), axis=1)
    pkdf['frame.len'] = pd.to_numeric(pkdf['frame.len'], errors='coerce')
    pkdf['frame.time_epoch'] = pd.to_numeric(pkdf['frame.time_epoch'], errors='coerce')
    # compute aggregates grouped by 5-tuple
    group_cols = ['ip.src','ip.dst','src_port','dst_port','proto']
    agg = pkdf.groupby(group_cols).agg(
        pkt_count = ('frame.len','count'),
        pkt_size_min = ('frame.len','min'),
        pkt_size_p25 = ('frame.len', lambda x: x.quantile(0.25)),
        pkt_size_p50 = ('frame.len', lambda x: x.quantile(0.5)),
        pkt_size_p75 = ('frame.len', lambda x: x.quantile(0.75)),
        pkt_size_max = ('frame.len','max'),
        pkt_size_mean = ('frame.len','mean'),
        pkt_size_std = ('frame.len','std'),
        first_ts = ('frame.time_epoch','min'),
        last_ts = ('frame.time_epoch','max'),
    ).reset_index()
    # compute iat metrics approx by sorting within group
    iat_rows = []
    for name, group in pkdf.groupby(group_cols):
        times = group['frame.time_epoch'].dropna().sort_values().values
        if len(times) <= 1:
            iat_mean = math.nan
            iat_median = math.nan
            iat_p90 = math.nan
        else:
            iats = times[1:] - times[:-1]
            iat_mean = float(np.mean(iats))
            iat_median = float(np.median(iats))
            iat_p90 = float(np.percentile(iats,90))
        row = dict(zip(group_cols, name))
        row.update({'iat_mean': iat_mean, 'iat_median': iat_median, 'iat_p90': iat_p90})
        iat_rows.append(row)
    iat_df = pd.DataFrame(iat_rows)
    merged = agg.merge(iat_df, on=group_cols, how='left')
    out_agg = out_dir / f"packet_aggregates_{Path(pcap_path).stem}.csv"
    merged.to_csv(out_agg, index=False)
    print("Wrote packet aggregates to", out_agg)
    return out_agg

def walk_and_process(zeek_root, out_root, pcap_manifest_path=None, do_packet_aggregates=False):
    zeek_root = Path(zeek_root)
    out_root = Path(out_root)
    safe_mkdir(out_root)
    # load pcap manifest if provided
    pcap_map = {}
    if pcap_manifest_path:
        pm = pd.read_csv(pcap_manifest_path)
        if 'pcap_id' in pm.columns and 'pcap_path' in pm.columns:
            pcap_map = dict(zip(pm['pcap_id'].astype(str), pm['pcap_path']))
        else:
            print("pcaps_manifest CSV must contain columns: pcap_id,pcap_path", file=sys.stderr)
    results_manifest = []
    # Walk directories
    for root, dirs, files in os.walk(zeek_root):
        # identify folders that contain zeek logs (look for .log files)
        log_files = [f for f in files if f.endswith('.log')]
        if not log_files:
            continue
        folder_path = Path(root)
        # derive pcap_id from folder names (best-effort):
        # assume structure .../<CLASS>/<SEQ>/<DEVICE>/zeek_logs
        parts = folder_path.parts
        pcap_id = "_".join(parts[-4:-1]) if len(parts) >= 3 else folder_path.name
        res, flows_df = process_folder(folder_path, out_root, pcap_id=pcap_id)
        entry = {'folder': str(folder_path), 'pcap_id': pcap_id}
        entry.update(res)
        results_manifest.append(entry)
        # optional packet aggregates
        if do_packet_aggregates and pcap_id in pcap_map:
            pcap_path = pcap_map[pcap_id]
            try:
                out_agg = compute_packet_aggregates_from_pcap(pcap_path, out_root)
                entry['packet_aggregates'] = str(out_agg) if out_agg is not None else ''
            except Exception as e:
                print("Packet aggregate error for", pcap_id, ":", e, file=sys.stderr)
    # save results manifest
    manifest_df = pd.DataFrame(results_manifest)
    manifest_csv = Path(out_root) / "zeek_to_csv_manifest.csv"
    manifest_df.to_csv(manifest_csv, index=False)
    print("Saved processing manifest to", manifest_csv)
    return manifest_df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zeek-root", required=True, help="Root folder that contains per-pcap zeek_logs folders")
    ap.add_argument("--out", required=True, help="Output root for CSVs")
    ap.add_argument("--pcaps-manifest", required=False, help="Optional CSV mapping pcap_id -> pcap_path for packet-level aggregates")
    ap.add_argument("--do-packet-aggregates", action='store_true', help="If set and pcaps manifest provided, run tshark and compute packet aggregates")
    args = ap.parse_args()
    manifest = walk_and_process(args.zeek_root, args.out, args.pcaps_manifest, args.do_packet_aggregates)
    print("Done. See output under:", args.out)

if __name__ == "__main__":
    main()
