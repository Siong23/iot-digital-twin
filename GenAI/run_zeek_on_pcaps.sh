#!/usr/bin/env bash
# run_zeek_on_pcaps.sh
# Usage:
#   ./run_zeek_on_pcaps.sh            # default: scan dataset/PCAPs and write to dataset/ZEEK_LOGS
#   ./run_zeek_on_pcaps.sh --force    # re-run Zeek even if conn.log exists
#   ./run_zeek_on_pcaps.sh --pcap-root path/to/PCAPs --zeek-root path/to/ZEEK_LOGS

set -euo pipefail
IFS=$'\n\t'

# Defaults (adjust if your layout differs)
PCAP_ROOT="dataset/PCAPs"
ZEEK_ROOT="dataset/ZEEK_LOGS"
FORCE=0

# Simple arg parsing
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift;;
    --pcap-root) PCAP_ROOT="$2"; shift 2;;
    --zeek-root) ZEEK_ROOT="$2"; shift 2;;
    -h|--help)
      cat <<EOF
Usage: $0 [--force] [--pcap-root PATH] [--zeek-root PATH]

--force         : re-run Zeek and overwrite existing zeek_logs (default: skip if conn.log exists)
--pcap-root PATH: root directory where PCAPs are stored (default: dataset/PCAPs)
--zeek-root PATH: root directory to write Zeek logs (default: dataset/ZEEK_LOGS)
EOF
      exit 0;;
    *)
      echo "Unknown arg: $1"
      exit 1;;
  esac
done

# Ensure zeek is installed
if ! command -v zeek >/dev/null 2>&1; then
  echo "ERROR: zeek not found in PATH. Install Zeek and retry."
  exit 2
fi

# Expand to absolute paths
PCAP_ROOT="$(realpath "$PCAP_ROOT")"
ZEEK_ROOT="$(realpath "$ZEEK_ROOT")"

echo "PCAP root: $PCAP_ROOT"
echo "Zeek output root: $ZEEK_ROOT"
echo "Force mode: $FORCE"
echo ""

# Find pcap files
mapfile -t PCAPS < <(find "$PCAP_ROOT" -type f \( -iname '*.pcap' -o -iname '*.pcapng' \) | sort)

if [ ${#PCAPS[@]} -eq 0 ]; then
  echo "No PCAP files found under $PCAP_ROOT"
  exit 0
fi

processed=0
skipped=0
errors=0
failed_list=()

for pcap in "${PCAPS[@]}"; do
  # compute relative path under PCAP_ROOT
  rel="${pcap#$PCAP_ROOT/}"        # e.g. Brute-force/1/DigitalBrokerServer/file.pcap
  # directory portion (Attack/run/path/device)
  rel_dir="$(dirname "$rel")"      # e.g. Brute-force/1/DigitalBrokerServer
  target_dir="$ZEEK_ROOT/$rel_dir/zeek_logs"

  echo "==="
  echo "PCAP: $pcap"
  echo "Target Zeek dir: $target_dir"

  mkdir -p "$target_dir" || { echo "Failed to create $target_dir"; errors=$((errors+1)); failed_list+=("$pcap"); continue; }

  # Skip if conn.log exists and not forcing
  if [ "$FORCE" -ne 1 ] && [ -f "$target_dir/conn.log" ]; then
    echo "Skipping (conn.log already exists). Use --force to re-run."
    skipped=$((skipped+1))
    continue
  fi

  # run Zeek inside the target_dir so the logs are written there
  # save stdout/stderr to zeek_run.log
  logfile="$target_dir/zeek_run.log"
  timestamp=$(date --iso-8601=seconds)
  echo "Run start: $timestamp" >> "$logfile"
  echo "zeek -r \"$pcap\"" >> "$logfile"

  # run zeek; capture exit status
  (
    cd "$target_dir"
    if zeek -r "$pcap" >> "$logfile" 2>&1; then
      echo "Zeek finished OK for $pcap (logs in $target_dir)" | tee -a "$logfile"
      processed=$((processed+1))
    else
      echo "Zeek failed for $pcap -- see $logfile" | tee -a "$logfile"
      errors=$((errors+1))
      failed_list+=("$pcap")
    fi
  )

done

echo "=== Summary ==="
echo "Total pcaps found : ${#PCAPS[@]}"
echo "Processed (ran Zeek): $processed"
echo "Skipped (existing conn.log): $skipped"
echo "Errors: $errors"
if [ ${#failed_list[@]} -gt 0 ]; then
  echo "Failed PCAPs:"
  for f in "${failed_list[@]}"; do echo " - $f"; done
fi

exit 0
