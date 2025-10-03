#!/usr/bin/env bash
# run_zeek_on_pcaps_local.sh
# Usage:
#   ./run_zeek_on_pcaps_local.sh            # default: scan dataset/PCAPs and write to dataset/ZEEK_LOGS
#   ./run_zeek_on_pcaps_local.sh --force    # re-run Zeek even if conn.log exists
#   ./run_zeek_on_pcaps_local.sh --pcap-root path/to/PCAPs --zeek-root path/to/ZEEK_LOGS

set -euo pipefail
IFS=$'\n\t'

PCAP_ROOT="dataset/PCAPs"
ZEEK_ROOT="dataset/ZEEK_LOGS"
FORCE=0

# Expected logs to check (tune if you want more/less)
EXPECTED_LOGS=(conn.log dns.log http.log tls.log ssl.log files.log notice.log mqtt_publish.log mqtt_connect.log mqtt_subcribe.log weird.log)

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

# Check zeek binary
if ! command -v zeek >/dev/null 2>&1; then
  echo "ERROR: zeek not found in PATH. Install Zeek and retry."
  exit 2
fi

PCAP_ROOT="$(realpath "$PCAP_ROOT")"
ZEEK_ROOT="$(realpath "$ZEEK_ROOT")"

echo "PCAP root: $PCAP_ROOT"
echo "Zeek output root: $ZEEK_ROOT"
echo "Force mode: $FORCE"
echo ""

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
  rel="${pcap#$PCAP_ROOT/}"
  rel_dir="$(dirname "$rel")"
  target_dir="$ZEEK_ROOT/$rel_dir/zeek_logs"
  mkdir -p "$target_dir" || { echo "Failed to create $target_dir"; errors=$((errors+1)); failed_list+=("$pcap"); continue; }

  echo "==="
  echo "PCAP: $pcap"
  echo "Target Zeek dir: $target_dir"

  if [ "$FORCE" -ne 1 ] && [ -f "$target_dir/conn.log" ]; then
    echo "Skipping (conn.log already exists). Use --force to re-run."
    skipped=$((skipped+1))
    continue
  fi

  logfile="$target_dir/zeek_run.log"
  timestamp=$(date --iso-8601=seconds)
  echo "Run start: $timestamp" >> "$logfile"
  echo "Running Zeek from PCAP dir and loading local scripts" >> "$logfile"

  pcap_dir="$(dirname "$pcap")"
  pcap_base="$(basename "$pcap")"

  (
    set -x
    cd "$pcap_dir"
    # Run Zeek from the PCAP folder so local.zeek loads. Use -C to ignore checksums and -s 65535 for full snaplen.
    # Note: 'local' tells Zeek to load the local.zeek/site-specific script.
    if zeek -C -s 65535 -r "$pcap" local >> "$logfile" 2>&1; then
      echo "Zeek finished OK for $pcap" >> "$logfile"
      # move produced logs out (if any). Use find to avoid moving unrelated files.
      shopt -s nullglob
      moved=0
      for f in *.log *.csv; do
        mv -f "$f" "$target_dir/" 2>/dev/null || true
        moved=1
      done
      # If Zeek writes logs to subdirs, move them too (rare)
      if [ $moved -eq 0 ]; then
        # nothing moved — maybe Zeek wrote logs directly to $target_dir (if ZEEKPATH altered); that's fine
        :
      fi
      processed=$((processed+1))
    else
      echo "Zeek failed for $pcap -- see $logfile" >> "$logfile"
      errors=$((errors+1)); failed_list+=("$pcap")
    fi
  )

  # After move, check for expected logs and warn if missing
  for e in "${EXPECTED_LOGS[@]}"; do
    if [ -f "$target_dir/$e" ]; then
      echo " ok: $e exists" >> "$logfile"
    else
      echo " warn: $e missing in $target_dir" >> "$logfile"
    fi
  done

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
