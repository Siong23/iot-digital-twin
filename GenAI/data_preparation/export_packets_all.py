#!/usr/bin/env python3
# export_packets_all.py
import subprocess, sys, os
from pathlib import Path

PCAP_ROOT = Path("dataset/PCAPs")
OUT_ROOT = Path("dataset/processed_dataset/packets")
OUT_ROOT.mkdir(parents=True, exist_ok=True)

# same fields as your extract_flow_packet_stats run_tshark_export
fields = [
    "-e", "frame.number",
    "-e", "frame.time_epoch",
    "-e", "ip.src", "-e", "ip.dst",
    "-e", "tcp.srcport","-e", "tcp.dstport",
    "-e", "udp.srcport","-e", "udp.dstport",
    "-e", "frame.len",
    "-e", "tcp.analysis.retransmission",
    "-e", "tcp.analysis.duplicate_ack",
    "-e", "ip.flags.mf",
    "-e", "tcp.flags"
]
header = ["frame_number","time_epoch","ip_src","ip_dst","tcp_srcport","tcp_dstport","udp_srcport","udp_dstport",
          "frame_len","tcp_retrans","tcp_dup_ack","ip_mf","tcp_flags"]

pcaps = list(PCAP_ROOT.rglob("*.pcap*"))
print(f"Found {len(pcaps)} pcaps")
failed = []
for p in pcaps:
    # derive pcap_id from path: Attack_Count_Path -> Attack_Count_Path (you can tune this)
    parts = p.parts
    # attempt to find Attack/Count/Path at end:
    if len(parts) >= 4:
        attack = parts[-4]
        count = parts[-3]
        path = parts[-2]
        pcap_id = f"{attack}_{count}_{path}"
    else:
        pcap_id = p.stem
    out_csv = OUT_ROOT / f"packets_{pcap_id}.csv"
    if out_csv.exists():
        print(f"Skipping existing {out_csv}")
        continue
    cmd = ["tshark", "-r", str(p), "-T", "fields", "-E", "separator=,", "-E", "quote=d", "-E", "occurrence=f"] + fields
    print("Running tshark for:", p, "->", out_csv)
    try:
        with open(out_csv, "w", encoding="utf-8") as out:
            out.write(",".join(header) + "\n")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)
            for line in proc.stdout:
                out.write(line)
            proc.stdout.close()
            rc = proc.wait()
            if rc != 0:
                stderr = proc.stderr.read()
                print(f"  tshark failed for {p}: rc={rc}\n{stderr}")
                failed.append(str(p))
                out.unlink(missing_ok=True)
    except FileNotFoundError:
        print("ERROR: tshark not found. Install tshark first.")
        sys.exit(2)
    except Exception as e:
        print("ERROR running tshark for", p, ":", e)
        failed.append(str(p))

print("Done. Failed:", len(failed))

