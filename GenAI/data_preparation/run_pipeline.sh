#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(pwd)"
PCAP_ROOT="$REPO_ROOT/dataset/PCAPs"
ZEEK_ROOT="$REPO_ROOT/dataset/ZEEK_LOGS"
PROCESSED_ROOT="$REPO_ROOT/dataset/processed_dataset"
PROCESSED_MODEL="$PROCESSED_ROOT/processed_for_model"

SCRIPTS_DIR="$REPO_ROOT/dataset/scripts"
ZEEK_RUN="$SCRIPTS_DIR/run_zeek_on_pcaps.sh"
Z2CSV_PY="$SCRIPTS_DIR/zeek_to_csv_minimal.py"
EXPORT_PACKETS_PY="$SCRIPTS_DIR/export_packets_all.py"
BUILD_SEQS_PY="$SCRIPTS_DIR/build_flow_packet_sequences_opt_all.py"
TOKENIZE_PY="$SCRIPTS_DIR/02_tokenize_packet_sequences.py"
BUILD_MASTER_PY="$SCRIPTS_DIR/01_build_master_flow_table_minimal.py"

echo "== Pipeline (minimal): produce flows_master.parquet + seqs_index.json + per-pcap seqs_*.npz = =="
echo "Repo root: $REPO_ROOT"

# quick checks
command -v zeek >/dev/null 2>&1 || { echo "ERROR: zeek not found in PATH"; exit 2; }
command -v tshark >/dev/null 2>&1 || { echo "ERROR: tshark not found in PATH"; exit 2; }
python3 - <<'PY' 2>/dev/null
import sys
reqs = ("pandas","numpy","pyarrow","tqdm")
missing = []
for r in reqs:
    try:
        __import__(r)
    except Exception:
        missing.append(r)
if missing:
    print("MISSING_PY:", ",".join(missing)); sys.exit(3)
print("PYREQS_OK")
PY
if [ $? -eq 3 ]; then
  echo "ERROR: python packages missing (install pandas,numpy,pyarrow,tqdm)."
  exit 3
fi

# prepare dirs
mkdir -p "$PROCESSED_ROOT/flows"
mkdir -p "$PROCESSED_ROOT/per_pcap_csvs"
mkdir -p "$PROCESSED_ROOT/packets"
mkdir -p "$PROCESSED_ROOT/seqs"
mkdir -p "$PROCESSED_MODEL"

echo "1) Run Zeek on PCAPs (skips processed ones)."
bash "$ZEEK_RUN" --pcap-root "$PCAP_ROOT" --zeek-root "$ZEEK_ROOT"

echo "2) Convert Zeek logs to per-pcap CSVs and minimal per-pcap flow CSVs"
python3 "$Z2CSV_PY" --zeek-root "$ZEEK_ROOT" --out-root "$PROCESSED_ROOT"

echo "3) Export packets CSVs from PCAPs (tshark)"
python3 "$EXPORT_PACKETS_PY"

echo "4) Build per-flow packet sequences (JSONL)"
python3 "$BUILD_SEQS_PY" --packets-dir "$PROCESSED_ROOT/packets" --conn-root "$PROCESSED_ROOT/per_pcap_csvs" --out-dir "$PROCESSED_ROOT/seqs"

echo "5) Tokenize/convert seqs JSONL -> per-pcap NPZ + seqs_index.json (processed_for_model)"
python3 "$TOKENIZE_PY" --max-len 200 --pad

echo "6) Build flows_master.parquet (final flow table)"
python3 "$BUILD_MASTER_PY"

echo ""
echo "=== DONE ==="
echo "Final artifacts (no monolithic NPZ):"
echo " - $PROCESSED_MODEL/flows_master.parquet"
echo " - $PROCESSED_MODEL/seqs_index.json"
echo " - per-pcap npz files: $PROCESSED_MODEL/seqs_*.npz"

