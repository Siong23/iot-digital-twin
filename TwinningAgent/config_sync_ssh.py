#!/usr/bin/env python3
"""
config_sync_ssh.py

Full-sync agent (physical -> digital) via SSH.
- Uses ~/.ssh/config host aliases "physical-router" and "digital-router"
- Rewrites interface names according to INTERFACE_MAP
- Rewrites any interface mentions (including flow-export source) with safe regex
- Syncs SNMP location/contact (and everything else)
- Saves snapshots and diffs; backs up digital config before applying
"""

import os
import re
import difflib
import datetime
import logging
from netmiko import ConnectHandler

# --------------------------- CONFIG ---------------------------
# SSH hosts must exist in ~/.ssh/config with BindAddress entries:
# Host physical-router  HostName 192.168.10.1  BindAddress 192.168.10.241 ...
# Host digital-router   HostName 192.168.10.1  BindAddress 192.168.10.242 ...
SSH_CONFIG_FILE = os.path.expanduser("~/.ssh/config")

PHYSICAL_ROUTER = {
    "device_type": "cisco_ios",
    "host": "physical-router",     # ssh alias in ~/.ssh/config
    "username": "admin",
    "password": "mmuzte123",
    "secret": "mmuzte123",
    "ssh_config_file": SSH_CONFIG_FILE,
}

DIGITAL_ROUTER = {
    "device_type": "cisco_ios",
    "host": "digital-router",      # ssh alias in ~/.ssh/config
    "username": "admin",
    "password": "mmuzte123",
    "secret": "mmuzte123",
    "ssh_config_file": SSH_CONFIG_FILE,
}

# Interface mapping: Physical -> Digital (user corrected)
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
def safe_regex_replace(text, mapping):
    """
    Replace each key in mapping with its value using word-boundary regex
    to avoid accidental partial replacements.
    """
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
def fetch_running_config(router):
    """SSH to router and fetch running-config."""
    logging.info(f"Connecting to {router['host']} to fetch running-config")
    conn = ConnectHandler(**router)
    conn.enable()
    out = conn.send_command("show running-config", delay_factor=2, max_loops=500)
    conn.disconnect()
    return out

def push_config(router, config_text):
    """Push a list of configuration lines to the router (entering config mode)."""
    logging.info(f"Pushing config to {router['host']}")
    conn = ConnectHandler(**router)
    conn.enable()
    # Build commands: remove comment lines and the "end" marker
    commands = []
    for line in config_text.splitlines():
        line = line.rstrip()
        if not line: 
            continue
        if line.startswith('!'):
            continue
        if line.lower().startswith('building configuration'):
            continue
        # avoid sending "end" explicitely; netmiko handles exit.
        if line.lower() == 'end':
            continue
        commands.append(line)
    # Send in small batches to avoid flooding
    conn.send_config_set(commands)
    conn.save_config()
    conn.disconnect()
    logging.info("Push complete and saved on device")

# --------------------------- MAIN LOGIC ---------------------------
def main():
    logging.info("=== Config sync run started ===")
    # 1) Fetch physical config
    physical_raw = fetch_running_config(PHYSICAL_ROUTER)

    # 2) Normalize line endings and remove initial non-config text
    # strip any leading "Building configuration" lines if present
    physical_normalized = "\n".join(
        line for line in physical_raw.splitlines()
        if not line.strip().lower().startswith("building configuration")
    )

    # 3) Map interfaces (safe regex mapping)
    physical_mapped = safe_regex_replace(physical_normalized, INTERFACE_MAP)

    # 4) Save snapshot
    phys_snapshot_file = save_text(physical_mapped, "physical")
    logging.info(f"Saved physical snapshot: {phys_snapshot_file}")

    # 5) Load previous physical config (if exists) and diff
    last_config = ""
    if os.path.exists(LAST_CONFIG_FILE):
        with open(LAST_CONFIG_FILE, "r") as f:
            last_config = f.read()

    diff_text = unified_diff(last_config, physical_mapped, fromfile="previous_physical.cfg", tofile="current_physical.cfg")
    if not diff_text.strip():
        logging.info("No change detected in physical config. Nothing to do.")
        print("[SYNC] No change detected.")
        return

    # 6) Save diff for review
    with open(DIFF_LOG, "w") as f:
        f.write(diff_text)
    logging.info("Differences detected; diff written to " + DIFF_LOG)
    print("[SYNC] Change detected; diff saved.")

    # 7) Backup current digital running-config
    digital_backup_raw = fetch_running_config(DIGITAL_ROUTER)
    backup_file = save_text(digital_backup_raw, f"digital_backup", directory=BACKUP_DIGITAL_DIR)
    logging.info(f"Backed up digital running-config to {backup_file}")

    # 8) The physical_mapped already has interfaces rewritten; but ensure any remaining
    # occurrences of interface names (e.g. flow-export source) are also mapped:
    to_push = safe_regex_replace(physical_mapped, INTERFACE_MAP)

    # 9) Special handling: ensure SNMP location/contact exist from physical and are present
    #    (they already are in the physical config and have been included in to_push via mapping)
    #    No extra action required unless you want to enforce different values.

    # 10) Push to digital
    try:
        push_config(DIGITAL_ROUTER, to_push)
    except Exception as e:
        logging.exception("Failed to push config to digital router: %s", e)
        print("[ERROR] Push failed:", e)
        return

    # 11) Update last physical config file after successful push
    with open(LAST_CONFIG_FILE, "w") as f:
        f.write(physical_mapped)

    # 12) Save a post-push backup of digital to confirm
    post_push = fetch_running_config(DIGITAL_ROUTER)
    post_file = save_text(post_push, "digital_postpush", directory=BACKUP_DIGITAL_DIR)
    logging.info(f"Saved post-push digital config to {post_file}")

    logging.info("=== Config sync run finished ===")
    print("[SYNC] Push succeeded. Diff and backups saved.")

if __name__ == "__main__":
    main()
