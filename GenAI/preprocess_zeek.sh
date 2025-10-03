#!/usr/bin/env bash
#
# preprocess_zeek.sh
#
# Usage:
#   edit the ZEEK_DIR and PCAP_ROOT variables below, then:
#     chmod +x preprocess_zeek.sh
#     ./preprocess_zeek.sh
#
# Requirements: zeek-cut (from Zeek), tshark (Wireshark), python3 with pandas and numpy
# Install Python deps: pip3 install pandas numpy
#
# What it produces (under OUTPUT_DIR):
#   - flows/<pcap_id>_flows.csv        (from conn.log)
#   - dns/<pcap_id>_dns.csv
#   - http/<pcap_id>_http.csv
#   - tls/<pcap_id>_tls.csv
#   - mqtt/<pcap_id>_mqtt.csv
#   - files/<pcap_id>_files.csv
#   - notices/<pcap_id>_notices.csv
#   - packets/<pcap_id>_packets.csv   (from tshark; only if PCAP found)
#   - packetstats/<pcap_id>_packetstats.csv   (per-flow aggregates; only if packets + flows exist)
#   - pcaps_manifest.csv               (summary rows)
#

set -euo pipefail
IFS=$'\n\t'

#### USER-CONFIGURABLE PATHS ####
ZEEK_DIR="${PWD}/ZEEK_LOGS"            # directory containing your per-folder zeek_logs folders
PCAP_ROOT="${PWD}/PCAPs"               # root where original PCAPs live (see note above)
OUTPUT_DIR="${PWD}/manifests"          # where all CSV outputs will be written
PYTHON_BIN="python3"
TSHARK_BIN="tshark"
ZEEK_CUT="zeek-cut"                    # ensure this is in PATH
CAPINFOS_BIN="capinfos"                # optional, for pcap manifest (if installed)
##################################

mkdir -p "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}/flows" "${OUTPUT_DIR}/dns" "${OUTPUT_DIR}/http" "${OUTPUT_DIR}/tls" \
         "${OUTPUT_DIR}/mqtt" "${OUTPUT_DIR}/files" "${OUTPUT_DIR}/notices" "${OUTPUT_DIR}/packets" \
         "${OUTPUT_DIR}/packetstats" "${OUTPUT_DIR}/logs"

MANIFEST_CSV="${OUTPUT_DIR}/pcaps_manifest.csv"

# Header for manifest
if [ ! -f "${MANIFEST_CSV}" ]; then
  echo "pcap_id,class,seq,device_type,zeek_folder,pcap_path,has_pcap,start_time_iso,end_time_iso,duration_s,packets,bytes,notes" > "${MANIFEST_CSV}"
fi

# helper: infer pcap path from zeek folder path (customize if needed)
# Example: ZEEK_DIR/Brute-force/1/DigitalBrokerServer/zeek_logs/  -> PCAP_ROOT/Brute-force/1/DigitalBrokerServer/*.pcap
infer_pcap_path() {
  local zeek_folder="$1"
  # remove trailing /zeek_logs if present
  local base="${zeek_folder%/zeek_logs}"
  # remove leading path (ZEEK_DIR)
  local rel="${base#${ZEEK_DIR}/}"
  echo "${PCAP_ROOT}/${rel}"
}

# embedded python aggregator will be written to a temp file
PY_AGG="${OUTPUT_DIR}/_aggregate_packets.py"
cat > "${PY_AGG}" <<'PYCODE'
#!/usr/bin/env python3
"""
Aggregate packet CSV into per-flow packet statistics.

Inputs (args):
  1) flows_csv_path  - CSV produced from conn.log (must contain 'uid','ts','id.orig_h','id.resp_h','id.orig_p','id.resp_p','duration')
  2) packets_csv_path - CSV produced by tshark with fields: frame_time_epoch, ip_src, ip_dst, tcp_srcport, tcp_dstport, frame_len, retrans, dupack, mf
  3) out_csv_path - where to write per-flow packet stats

Matching strategy:
  - Prefer matching by Zeek UID (if packet CSV contains 'uid' column).
  - Otherwise match by 5-tuple (ip/src/dst/ports or swapped) and timestamp inside flow start..end.
"""
import sys, os, math
import pandas as pd
import numpy as np

if len(sys.argv) != 4:
    print("Usage: aggregate_packets.py <flows_csv> <packets_csv> <out_csv>")
    sys.exit(2)

flows_csv, packets_csv, out_csv = sys.argv[1:]

# read flows
flows = pd.read_csv(flows_csv)
if 'ts' not in flows.columns:
    # try alternative
    if 'start_time' in flows.columns:
        flows['ts'] = flows['start_time']
    else:
        raise SystemExit("flows CSV must have 'ts' column (flow start timestamp)")

# Normalize columns expected
for col in ['id.orig_h','id.resp_h','id.orig_p','id.resp_p','duration','uid']:
    if col not in flows.columns:
        # insert blanks if missing (to avoid crash)
        flows[col] = np.nan

flows['ts'] = pd.to_numeric(flows['ts'], errors='coerce').astype(float)
flows['duration'] = pd.to_numeric(flows['duration'], errors='coerce').fillna(0).astype(float)
flows['ts_end'] = flows['ts'] + flows['duration']

# read packets
pk = pd.read_csv(packets_csv)
# expected fields: frame_time_epoch, ip.src/ip.dst, tcp.srcport/tcp.dstport, frame.len, retrans (0/1), dupack (0/1), mf (0/1)
# try several possible header variants
col_map = {}
for c in pk.columns:
    lc = c.lower()
    if 'time' in lc and ('epoch' in lc or 'frame.time_epoch' in lc):
        col_map['time'] = c
    if lc.endswith('ip.src') or lc == 'ip.src' or lc == 'ip_source':
        col_map['ip_src'] = c
    if lc.endswith('ip.dst') or lc == 'ip.dst' or lc == 'ip_dest':
        col_map['ip_dst'] = c
    if 'tcp.srcport' in lc or 'tcp.srcport' == lc or 'tcp.src_port' in lc:
        col_map['sport'] = c
    if 'tcp.dstport' in lc or 'tcp.dstport' == lc or 'tcp.dst_port' in lc:
        col_map['dport'] = c
    if 'frame.len' in lc or 'length' in lc or 'frame_length' in lc:
        col_map['len'] = c
    if 'retrans' in lc:
        col_map['retrans'] = c
    if 'duplicate' in lc or 'dupack' in lc:
        col_map['dupack'] = c
    if 'mf' == lc or 'ip.flags.mf' in lc:
        col_map['mf'] = c
    if lc == 'uid':
        col_map['uid'] = c

required = ['time','ip_src','ip_dst','sport','dport','len']
for r in required:
    if r not in col_map:
        print(f"Packet CSV missing required column matching '{r}'. Found columns: {list(pk.columns)}")
        # proceed but may fail grouping

# rename for convenience (only those found)
rename_map = {v:k for k,v in col_map.items()}
pk = pk.rename(columns=rename_map)
# ensure types
pk['time'] = pd.to_numeric(pk['time'], errors='coerce').astype(float)
pk['len'] = pd.to_numeric(pk['len'], errors='coerce').astype(float)
if 'retrans' in pk.columns:
    pk['retrans'] = pk['retrans'].fillna(0).astype(int)
else:
    pk['retrans'] = 0
if 'dupack' in pk.columns:
    pk['dupack'] = pk['dupack'].fillna(0).astype(int)
else:
    pk['dupack'] = 0
if 'mf' in pk.columns:
    pk['mf'] = pk['mf'].fillna(0).astype(int)
else:
    pk['mf'] = 0

# Helper: create normalized 5-tuple key (direction-agnostic)
def tuple_key(row):
    s = str(row.get('ip_src',''))+":"+str(row.get('sport',''))+"-"+str(row.get('ip_dst',''))+":"+str(row.get('dport',''))
    s_rev = str(row.get('ip_dst',''))+":"+str(row.get('dport',''))+"-"+str(row.get('ip_src',''))+":"+str(row.get('sport',''))
    return (s, s_rev)

# If uid exists in both, use direct mapping
use_uid = ('uid' in flows.columns) and ('uid' in pk.columns)
if use_uid:
    pk_grp = pk.groupby('uid')
    stats_rows = []
    for uid, g in pk_grp:
        lens = g['len'].dropna().values
        if len(lens)==0:
            continue
        times = np.sort(g['time'].values)
        iats = np.diff(times) if len(times)>1 else np.array([0.0])
        stats = {
            'uid': uid,
            'pkt_count': int(len(lens)),
            'pkt_len_min': float(np.min(lens)),
            'pkt_len_p25': float(np.percentile(lens,25)),
            'pkt_len_p50': float(np.percentile(lens,50)),
            'pkt_len_p75': float(np.percentile(lens,75)),
            'pkt_len_max': float(np.max(lens)),
            'pkt_len_mean': float(np.mean(lens)),
            'pkt_len_std': float(np.std(lens)),
            'iat_mean': float(np.mean(iats)) if len(iats)>0 else 0.0,
            'iat_p90': float(np.percentile(iats,90)) if len(iats)>0 else 0.0,
            'retrans_count': int(g['retrans'].sum()) if 'retrans' in g.columns else 0,
            'dupack_count': int(g['dupack'].sum()) if 'dupack' in g.columns else 0,
            'frag_count': int(g['mf'].sum()) if 'mf' in g.columns else 0
        }
        stats_rows.append(stats)
    outdf = pd.DataFrame(stats_rows)
    outdf.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} (uid grouped)")
    sys.exit(0)

# Otherwise, attempt time + 5-tuple matching:
# Precompute keys for flows and packets
flows['tuple_fwd'] = flows['id.orig_h'].astype(str) + ":" + flows['id.orig_p'].astype(str) + "-" + flows['id.resp_h'].astype(str) + ":" + flows['id.resp_p'].astype(str)
flows['tuple_rev'] = flows['id.resp_h'].astype(str) + ":" + flows['id.resp_p'].astype(str) + "-" + flows['id.orig_h'].astype(str) + ":" + flows['id.orig_p'].astype(str)

pk['tuple'] = pk['ip_src'].astype(str) + ":" + pk['sport'].astype(str) + "-" + pk['ip_dst'].astype(str) + ":" + pk['dport'].astype(str)
pk['tuple_rev'] = pk['ip_dst'].astype(str) + ":" + pk['dport'].astype(str) + "-" + pk['ip_src'].astype(str) + ":" + pk['sport'].astype(str)

# For each flow, find candidate packets matching either tuple or tuple_rev and time inside range
stats_rows = []
pk_indexed = pk.sort_values('time')
for idx, f in flows.iterrows():
    start = float(f['ts'])
    end = float(f['ts_end'])
    t1 = str(f['tuple_fwd'])
    t2 = str(f['tuple_rev'])
    # select candidate pk rows (naive filter)
    candidate = pk_indexed[( (pk_indexed['tuple']==t1) | (pk_indexed['tuple']==t2) | (pk_indexed['tuple_rev']==t1) | (pk_indexed['tuple_rev']==t2) )
                           & (pk_indexed['time'] >= (start - 0.0005)) & (pk_indexed['time'] <= (end + 0.0005))]
    if candidate.shape[0]==0:
        continue
    lens = candidate['len'].dropna().values
    times = np.sort(candidate['time'].values)
    iats = np.diff(times) if len(times)>1 else np.array([0.0])
    stats = {
        'flow_index': int(idx),
        'uid': f.get('uid', ''),
        'pkt_count': int(len(lens)),
        'pkt_len_min': float(np.min(lens)),
        'pkt_len_p25': float(np.percentile(lens,25)),
        'pkt_len_p50': float(np.percentile(lens,50)),
        'pkt_len_p75': float(np.percentile(lens,75)),
        'pkt_len_max': float(np.max(lens)),
        'pkt_len_mean': float(np.mean(lens)),
        'pkt_len_std': float(np.std(lens)),
        'iat_mean': float(np.mean(iats)) if len(iats)>0 else 0.0,
        'iat_p90': float(np.percentile(iats,90)) if len(iats)>0 else 0.0,
        'retrans_count': int(candidate['retrans'].sum()) if 'retrans' in candidate.columns else 0,
        'dupack_count': int(candidate['dupack'].sum()) if 'dupack' in candidate.columns else 0,
        'frag_count': int(candidate['mf'].sum()) if 'mf' in candidate.columns else 0
    }
    stats_rows.append(stats)
outdf = pd.DataFrame(stats_rows)
outdf.to_csv(out_csv, index=False)
print(f"Wrote {out_csv} (matched by 5-tuple+time for {len(outdf)} flows)")
PYCODE

chmod +x "${PY_AGG}"

echo "Starting processing of Zeek logs under: ${ZEEK_DIR}"
echo "PCAP root (for packet extraction): ${PCAP_ROOT}"
echo "Outputs going to: ${OUTPUT_DIR}"
echo ""

# find all zeek_logs directories (assume those are directories ending with 'zeek_logs')
while IFS= read -r -d '' zeek_folder; do
  # zeek_folder is like .../Brute-force/1/DigitalBrokerServer/zeek_logs
  relpath="${zeek_folder#${ZEEK_DIR}/}"     # e.g. Brute-force/1/DigitalBrokerServer/zeek_logs
  # create a compact pcap_id (replace / with __ and remove trailing /zeek_logs)
  pcap_dir_base="${relpath%/zeek_logs}"
  pcap_id="$(echo "${pcap_dir_base}" | sed 's/[\/ ]/_/g')"
  class="$(echo "${pcap_dir_base}" | cut -d'/' -f1 || echo '')"
  seq="$(echo "${pcap_dir_base}" | cut -d'/' -f2 || echo '')"
  device_type="$(echo "${pcap_dir_base}" | cut -d'/' -f3- | sed 's|/|_|g' || echo '')"

  out_flows="${OUTPUT_DIR}/flows/${pcap_id}_flows.csv"
  out_dns="${OUTPUT_DIR}/dns/${pcap_id}_dns.csv"
  out_http="${OUTPUT_DIR}/http/${pcap_id}_http.csv"
  out_tls="${OUTPUT_DIR}/tls/${pcap_id}_tls.csv"
  out_mqtt="${OUTPUT_DIR}/mqtt/${pcap_id}_mqtt.csv"
  out_files="${OUTPUT_DIR}/files/${pcap_id}_files.csv"
  out_notices="${OUTPUT_DIR}/notices/${pcap_id}_notices.csv"
  out_packets="${OUTPUT_DIR}/packets/${pcap_id}_packets.csv"
  out_packetstats="${OUTPUT_DIR}/packetstats/${pcap_id}_packetstats.csv"

  echo "Processing: ${relpath} -> pcap_id=${pcap_id}"

  # 1) Extract conn.log (flows) if exists
  if [ -f "${zeek_folder}/conn.log" ]; then
    echo "  extracting conn.log -> ${out_flows}"
    # header
    echo "ts,uid,id.orig_h,id.resp_h,id.orig_p,id.resp_p,proto,service,duration,orig_pkts,resp_pkts,orig_bytes,resp_bytes,conn_state,history" > "${out_flows}"
    ${ZEEK_CUT} ts uid id.orig_h id.resp_h id.orig_p id.resp_p proto service duration orig_pkts resp_pkts orig_bytes resp_bytes conn_state history < "${zeek_folder}/conn.log" \
      | sed 's/\t/,/g' >> "${out_flows}" || echo "    zeek-cut conn failed for ${zeek_folder}, skipping conn extraction"
  else
    echo "  WARNING: conn.log not found in ${zeek_folder}"
  fi

  # 2) Extract dns.log
  if [ -f "${zeek_folder}/dns.log" ]; then
    echo "  extracting dns.log -> ${out_dns}"
    echo "ts,uid,id.orig_h,query,qtype_name,rcode_name,answers,ttl" > "${out_dns}"
    ${ZEEK_CUT} ts uid id.orig_h query qtype_name rcode_name answers ttl < "${zeek_folder}/dns.log" | sed 's/\t/,/g' >> "${out_dns}" || true
  fi

  # 3) Extract http.log
  if [ -f "${zeek_folder}/http.log" ]; then
    echo "  extracting http.log -> ${out_http}"
    echo "ts,uid,id.orig_h,id.resp_h,method,host,uri,user_agent,status_code,resp_mime_types" > "${out_http}"
    ${ZEEK_CUT} ts uid id.orig_h id.resp_h method host uri user_agent status_code resp_mime_types < "${zeek_folder}/http.log" | sed 's/\t/,/g' >> "${out_http}" || true
  fi

  # 4) Extract tls/ssl.log
  if [ -f "${zeek_folder}/tls.log" ]; then
    echo "  extracting tls.log -> ${out_tls}"
    echo "ts,uid,id.orig_h,id.resp_h,version,cipher,server_name,ja3" > "${out_tls}"
    ${ZEEK_CUT} ts uid id.orig_h id.resp_h version cipher server_name ja3 < "${zeek_folder}/tls.log" | sed 's/\t/,/g' >> "${out_tls}" || true
  elif [ -f "${zeek_folder}/ssl.log" ]; then
    echo "  extracting ssl.log -> ${out_tls}"
    echo "ts,uid,id.orig_h,id.resp_h,version,cipher,server_name" > "${out_tls}"
    ${ZEEK_CUT} ts uid id.orig_h id.resp_h version cipher server_name < "${zeek_folder}/ssl.log" | sed 's/\t/,/g' >> "${out_tls}" || true
  fi

  # 5) Extract mqtt logs (connect/publish/subscribe) (if present)
  if [ -f "${zeek_folder}/mqtt_publish.log" ] || [ -f "${zeek_folder}/mqtt_connect.log" ] || [ -f "${zeek_folder}/mqtt_subcribe.log" ]; then
    echo "  extracting MQTT logs -> ${out_mqtt}"
    echo "ts,uid,mqtt_type,client_id,topic,payload_len,qos,retain" > "${out_mqtt}"
    if [ -f "${zeek_folder}/mqtt_connect.log" ]; then
      ${ZEEK_CUT} ts uid client_id < "${zeek_folder}/mqtt_connect.log" | sed 's/\t/,/g' | awk -F',' '{print $1","$2",CONNECT,"$3",,,"}' >> "${out_mqtt}" || true
    fi
    if [ -f "${zeek_folder}/mqtt_publish.log" ]; then
      # the fields here depend on your Zeek script; attempt to extract common ones
      ${ZEEK_CUT} ts uid topic payload_len qos retain client_id < "${zeek_folder}/mqtt_publish.log" 2>/dev/null | sed 's/\t/,/g' | awk -F',' '{print $1","$2",PUBLISH,"$7","$3","$4","$5}' >> "${out_mqtt}" || true
    fi
    if [ -f "${zeek_folder}/mqtt_subcribe.log" ]; then
      ${ZEEK_CUT} ts uid topic client_id < "${zeek_folder}/mqtt_subcribe.log" | sed 's/\t/,/g' | awk -F',' '{print $1","$2",SUBSCRIBE,"$3","$1",,}' >> "${out_mqtt}" || true
    fi
  fi

  # 6) Extract files.log
  if [ -f "${zeek_folder}/files.log" ]; then
    echo "  extracting files.log -> ${out_files}"
    echo "ts,uid,fuid,source,filename,tx_bytes,duration,mime_type" > "${out_files}"
    ${ZEEK_CUT} ts uid fuid source filename tx_bytes duration mime_type < "${zeek_folder}/files.log" | sed 's/\t/,/g' >> "${out_files}" || true
  fi

  # 7) Extract notices/weird if any
  if [ -f "${zeek_folder}/notice.log" ]; then
    echo "  extracting notice.log -> ${out_notices}"
    echo "ts,uid,note,msg,sub,notice_id,priority" > "${out_notices}"
    ${ZEEK_CUT} ts uid note msg sub note_id priority < "${zeek_folder}/notice.log" | sed 's/\t/,/g' >> "${out_notices}" || true
  elif [ -f "${zeek_folder}/weird.log" ]; then
    echo "  extracting weird.log -> ${out_notices}"
    echo "ts,uid,what,uid2,sub,notice_id" > "${out_notices}"
    ${ZEEK_CUT} ts uid what uid2 sub note_id < "${zeek_folder}/weird.log" | sed 's/\t/,/g' >> "${out_notices}" || true
  fi

  # 8) Try to find corresponding pcap(s)
  pcap_search_dir="$(infer_pcap_path "${zeek_folder}")"
  found_pcap=""
  if [ -d "${pcap_search_dir}" ]; then
    # prefer the largest pcap (if multiple) to match full capture
    found_pcap="$(ls -1S "${pcap_search_dir}"/*.pcap 2>/dev/null | head -n1 || true)"
  fi

  has_pcap="NO"
  start_time=""
  end_time=""
  duration_s=""
  pkt_count=""
  total_bytes=""

  if [ -n "${found_pcap}" ] && [ -f "${found_pcap}" ]; then
    has_pcap="YES"
    echo "  found pcap: ${found_pcap}  -> exporting packets CSV"
    # export packets with tshark
    # fields: frame.time_epoch, ip.src, ip.dst, tcp.srcport, tcp.dstport, frame.len, tcp.analysis.retransmission, tcp.analysis.duplicate_ack, ip.flags.mf
    "${TSHARK_BIN}" -r "${found_pcap}" -T fields -E separator=, \
      -e frame.time_epoch -e ip.src -e ip.dst -e tcp.srcport -e tcp.dstport -e frame.len -e tcp.analysis.retransmission -e tcp.analysis.duplicate_ack -e ip.flags.mf \
      > "${out_packets}" 2> "${OUTPUT_DIR}/logs/tshark_${pcap_id}.log" || echo "    tshark failed for ${found_pcap}, see logs"
    # attempt to get basic pcap stats with capinfos if available
    if command -v "${CAPINFOS_BIN}" >/dev/null 2>&1; then
      infos=$(${CAPINFOS_BIN} -a -u -M -P -c -T "${found_pcap}" 2>/dev/null || true)
      # capinfos output is multi-line; extract packet count and first/last times approx
      pkt_count=$(echo "${infos}" | awk -F',' '/Number of packets/{print $2}' | tr -d ' ')
      # fallback: we can attempt to fetch start/end with tshark
    fi
    # fallback timestamps via tshark (fast)
    # get first and last frame time
    first_time=$("${TSHARK_BIN}" -r "${found_pcap}" -T fields -e frame.time_epoch | head -n1)
    last_time=$("${TSHARK_BIN}" -r "${found_pcap}" -T fields -e frame.time_epoch | tail -n1)
    if [ -n "${first_time}" ] && [ -n "${last_time}" ]; then
      start_time="$(date -u -d "@${first_time}" --iso-8601=seconds 2>/dev/null || printf "%s" "${first_time}")"
      end_time="$(date -u -d "@${last_time}" --iso-8601=seconds 2>/dev/null || printf "%s" "${last_time}")"
      duration_s=$(awk "BEGIN {print ${last_time} - ${first_time}}")
    fi

    # 9) compute packetstats by joining flows + packets (only if flows csv exists)
    if [ -f "${out_flows}" ] && [ -s "${out_packets}" ]; then
      echo "  computing packet-level aggregates -> ${out_packetstats}"
      "${PYTHON_BIN}" "${PY_AGG}" "${out_flows}" "${out_packets}" "${out_packetstats}"
    else
      echo "  skipping packetstats: missing flows or packets CSV"
    fi
  else
    echo "  no matching PCAP found at ${pcap_search_dir} (skipping packet export and packetstats)"
  fi

  # append manifest row
  notes=""
  echo "${pcap_id},${class},${seq},${device_type},\"${zeek_folder}\",\"${found_pcap}\",${has_pcap},${start_time},${end_time},${duration_s},${pkt_count},${total_bytes},\"${notes}\"" >> "${MANIFEST_CSV}"

  echo "  done ${pcap_id}"
  echo ""

done < <(find "${ZEEK_DIR}" -type d -name "zeek_logs" -print0)

echo "Processing complete. Summary manifest: ${MANIFEST_CSV}"
echo "Per-log CSVs are in ${OUTPUT_DIR} (flows,dns,http,tls,mqtt,files,notices,packets,packetstats)."
echo "If some packetstats are missing, ensure PCAP_ROOT points to the directory containing corresponding PCAP files."
