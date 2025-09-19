#!/usr/bin/env python3
"""
config_sync_ssh.py

Full-sync agent (physical -> digital) via SSH with source-IP binding.
- Explicitly binds 192.168.10.241 for physical, 192.168.10.242 for digital
- Rewrites interface names according to INTERFACE_MAP
- Syncs SNMP location/contact + all other configs
- Backs up configs, diffs, and applies only when change is detected
"""

import os
import re
import difflib
import datetime
import logging
import socket
from netmiko import ConnectHandler

# --------------------------- CONFIG ---------------------------

PHYSICAL_ROUTER = {
    "device_type": "cisco_ios",
    "host": "192.168.10.1",
    "username": "admin",
    "password": "mmuzte123",
    "secret": "mmuzte123",
}
DIGITAL_ROUTER = {
    "device_type": "cisco_ios",
    "host": "192.168.10.1",
    "username": "admin",
    "password": "mmuzte123",
    "secret": "mmuzte123",
}

PHYS_BIND = "192.168.10.241"
DIGI_BIND = "192.168.10.242"

# Interface mapping: Physical -> Digital
INTERFACE_MAP = {
    "GigabitEthernet0/1": "GigabitEthernet2/0",
    "GigabitEthernet0/2": "GigabitEthernet1/0",
    "GigabitEthernet0/3": "GigabitEthernet0/0",
}

# Paths
CONFIG_DIR = "configs"
LAST_CONFIG_FILE = os.path.join(CONFIG_DIR, "previous_physical.cfg")
DIFF_LOG = os.path.join(CONFIG_DIR, "last_diff.patch")
BACKUP_DIGITAL_DIR = os.path.join(CONFIG_DIR, "digital_backups")

# Logging
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIGITAL_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(CONFIG_DIR, "config_sync.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

# --------------------------- UTILITIES ---------------------------

def connect_with_source(router, source_ip):
    """Force SSH connection with specific source IP."""
    sock = socket.create_connection(
        (router["host"], 22),
        source_address=(source_ip, 0)
    )
    conn = ConnectHandler(**router, sock=sock)
    conn.enable()
    return conn

def safe_regex_replace(text, mapping):
    for src, dst in mapping.items():
        pattern = r'\b' + re.escape(src) + r'\b'
        text = re.sub(pattern, dst, text)
    return text

def save_text(text, prefix, directory=CONFIG_DIR):
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fn = os.path.join(directory, f"{prefix}_{ts}.cfg")
    with open(fn, "w") as f:
        f.write(text)
    return fn

def unified_diff(a, b, fromfile="old", tofile="new"):
    return "\n".join(difflib.unified_diff(
        a.splitlines(), b.splitlines(),
        fromfile=fromfile, tofile=tofile, lineterm=""
    ))

# --------------------------- CORE ACTIONS ---------------------------

def fetch_running_config(router, bind_ip):
    logging.info(f"Fetching running-config from {router['host']} via {bind_ip}")
    conn = connect_with_source(router, bind_ip)
    conn.send_command("terminal length 0")
    out = conn.send_command("show running-config", use_textfsm=False, delay_factor=2, max_loops=1000)
    conn.disconnect()
    return out

def push_config(router, bind_ip, config_text):
    logging.info(f"Pushing config to {router['host']} via {bind_ip}")
    conn = connect_with_source(router, bind_ip)
    commands = []
    for line in config_text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("!") or line.lower() in ["end", "building configuration..."]:
            continue
        commands.append(line)
    if commands:
        conn.send_config_set(commands)
        conn.save_config()
    conn.disconnect()
    logging.info("Push complete and saved on device")

# --------------------------- MAIN LOGIC ---------------------------

def main():
    logging.info("=== Config sync run started ===")

    # 1) Fetch physical config
    physical_raw = fetch_running_config(PHYSICAL_ROUTER, PHYS_BIND)

    physical_normalized = "\n".join(
        line for line in physical_raw.splitlines()
        if not line.strip().lower().startswith("building configuration")
    )

    # 2) Map interfaces
    physical_mapped = safe_regex_replace(physical_normalized, INTERFACE_MAP)

    # 3) Save snapshot
    phys_snapshot_file = save_text(physical_mapped, "physical")
    logging.info(f"Saved physical snapshot: {phys_snapshot_file}")

    # 4) Compare to previous
    last_config = ""
    if os.path.exists(LAST_CONFIG_FILE):
        with open(LAST_CONFIG_FILE, "r") as f:
            last_config = f.read()

    diff_text = unified_diff(last_config, physical_mapped,
                             fromfile="previous_physical.cfg",
                             tofile="current_physical.cfg")

    if not diff_text.strip():
        logging.info("No change detected in physical config.")
        print("[SYNC] No change detected.")
        return

    with open(DIFF_LOG, "w") as f:
        f.write(diff_text)
    logging.info(f"Diff saved to {DIFF_LOG}")
    print("[SYNC] Change detected; diff saved.")

    # 5) Backup current digital
    digital_backup_raw = fetch_running_config(DIGITAL_ROUTER, DIGI_BIND)
    backup_file = save_text(digital_backup_raw, "digital_backup", directory=BACKUP_DIGITAL_DIR)
    logging.info(f"Backed up digital running-config to {backup_file}")

    # 6) Prepare config for push
    to_push = safe_regex_replace(physical_mapped, INTERFACE_MAP)

    # 7) Push
    try:
        push_config(DIGITAL_ROUTER, DIGI_BIND, to_push)
    except Exception as e:
        logging.exception("Push failed: %s", e)
        print("[ERROR] Push failed:", e)
        return

    # 8) Update last physical config
    with open(LAST_CONFIG_FILE, "w") as f:
        f.write(physical_mapped)

    # 9) Save post-push digital
    post_push = fetch_running_config(DIGITAL_ROUTER, DIGI_BIND)
    post_file = save_text(post_push, "digital_postpush", directory=BACKUP_DIGITAL_DIR)
    logging.info(f"Saved post-push digital config to {post_file}")

    logging.info("=== Config sync run finished ===")
    print("[SYNC] Push succeeded. Diff and backups saved.")

if __name__ == "__main__":
    main()
