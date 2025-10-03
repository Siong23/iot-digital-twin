import os
import pandas as pd
from pathlib import Path

# Root folder where all your attack folders (Brute-force, DDoS, MQTT, etc.) live
ROOT_DIR = "ZEEK_LOGS"   # <-- change if needed

# Logs we care most about (others can be added if relevant)
IMPORTANT_LOGS = [
    "conn.log", "dns.log", "http.log", "ssl.log", "tls.log",
    "files.log", "notice.log", "weird.log", "mqtt_connect.log",
    "mqtt_publish.log", "mqtt_subcribe.log"
]

# Where to save output
OUTPUT_DIR = "csv_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_zeek_log(filepath):
    """
    Parse a Zeek TSV-style log file into a DataFrame.
    Ignores lines starting with '#'.
    """
    with open(filepath, "r") as f:
        lines = [line.strip() for line in f if not line.startswith("#")]
    if not lines:
        return pd.DataFrame()
    # Zeek logs are tab-delimited
    df = pd.read_csv(filepath, sep="\t", comment="#", low_memory=False)
    return df

all_dfs = []

for root, dirs, files in os.walk(ROOT_DIR):
    for file in files:
        if file.endswith(".log") and file in IMPORTANT_LOGS:
            fpath = os.path.join(root, file)

            # Extract metadata from folder structure: Attack/Run/Device
            parts = Path(fpath).parts
            # Example: Brute-force/1/DigitalBrokerServer/zeek_logs/conn.log
            try:
                attack_type = parts[-4]
                run_id     = parts[-3]
                device     = parts[-2]
            except IndexError:
                attack_type, run_id, device = "Unknown", "Unknown", "Unknown"

            df = parse_zeek_log(fpath)
            if df.empty:
                continue

            # Add metadata
            df["attack_type"] = attack_type
            df["run_id"] = run_id
            df["device"] = device
            df["log_type"] = file.replace(".log","")

            # Save individual CSV per log file
            out_folder = os.path.join(OUTPUT_DIR, attack_type, run_id, device)
            os.makedirs(out_folder, exist_ok=True)
            out_file = os.path.join(out_folder, file.replace(".log",".csv"))
            df.to_csv(out_file, index=False)

            # Add to global collector
            all_dfs.append(df)

# Combine all into one big CSV
if all_dfs:
    master = pd.concat(all_dfs, ignore_index=True)
    master_out = os.path.join(OUTPUT_DIR, "all_flows.csv")
    master.to_csv(master_out, index=False)
    print(f"[+] Combined CSV written to {master_out} with {len(master)} rows")
else:
    print("[-] No Zeek logs parsed")
