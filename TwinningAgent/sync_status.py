#!/usr/bin/env python3
"""
sync_status.py
---------------
Proxy agent to synchronize UP/DOWN status between physical and digital twins.

- Pings each physical device via bind_ip
- If physical is DOWN, stop corresponding digital node in GNS3
- If physical is UP, start corresponding digital node in GNS3 (if stopped)
"""

import os
import time
import yaml
import subprocess
import requests
import logging
from requests.auth import HTTPBasicAuth

# ---------------- CONFIG ----------------
CONFIG_FILE = "devices.yaml"
PING_COUNT = 1       # number of ICMP packets
PING_TIMEOUT = 2     # seconds
CHECK_INTERVAL = 60  # how often to check in seconds

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename="sync_status.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------- HELPERS ----------------
def ping(ip, bind_ip=None):
    """Ping an IP from a specific source IP."""
    try:
        cmd = ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT)]
        if bind_ip:
            cmd.extend(["-I", bind_ip])
        cmd.append(ip)
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception as e:
        logging.error(f"Ping error {ip} via {bind_ip}: {e}")
        return False

def gns3_request(cfg, method, endpoint):
    """Send REST request to GNS3 server with auth."""
    url = f"{cfg['url'].rstrip('/')}{endpoint}"
    try:
        r = requests.request(
            method, url,
            auth=HTTPBasicAuth(cfg["user"], cfg["password"]),
            timeout=5
        )
        if not r.ok:
            logging.error(f"GNS3 API {method} {url} failed: {r.status_code} {r.text}")
        return r
    except Exception as e:
        logging.error(f"GNS3 API error {url}: {e}")
        return None

def stop_node(cfg, project_id, node_id):
    logging.info(f"Stopping digital node {node_id}")
    return gns3_request(cfg, "POST", f"/projects/{project_id}/nodes/{node_id}/stop")

def start_node(cfg, project_id, node_id):
    logging.info(f"Starting digital node {node_id}")
    return gns3_request(cfg, "POST", f"/projects/{project_id}/nodes/{node_id}/start")

# ---------------- MAIN ----------------
def main():
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)

    gns3_cfg = config["gns3"]
    project_id = gns3_cfg["project_id"]

    devices_phys = config["devices"]["physical"]
    devices_digi = config["devices"]["digital"]

    # track last status
    last_status = {}

    logging.info("=== Sync agent started ===")

    while True:
        for name, phys in devices_phys.items():
            ip = phys["ip"]
            bind_ip = phys.get("bind_ip")
            is_up = ping(ip, bind_ip)
            logging.info(f"Ping {name} ({ip}) via {bind_ip}: {'UP' if is_up else 'DOWN'}")

            digi = devices_digi.get(name)
            if not digi:
                continue  # no digital twin defined

            node_id = digi.get("gns3_node_id")
            if not node_id:
                continue  # digital node ID missing

            prev = last_status.get(name)
            if prev == is_up:
                continue  # status unchanged

            # if physical is down → stop digital
            if not is_up:
                stop_node(gns3_cfg, project_id, node_id)
            else:
                start_node(gns3_cfg, project_id, node_id)

            last_status[name] = is_up

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
