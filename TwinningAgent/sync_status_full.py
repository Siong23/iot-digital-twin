#!/usr/bin/env python3
"""
sync_status_full.py
-------------------
Proxy agent to synchronize UP/DOWN status and per-connection health
between physical and digital twins.

- Pings physical devices directly (proxy check)
- Listens to MQTT health reports from devices (e.g. router probe, sensor probe)
- If device or connection is DOWN → stop or block corresponding digital twin
- Holds blocks until explicit UP is received OR safety timeout expires

Requires:
    pip install pyyaml requests paho-mqtt
"""

import os, time, yaml, subprocess, logging, json, threading
import requests
from requests.auth import HTTPBasicAuth
import paho.mqtt.client as mqtt

# ---------------- CONFIG ----------------
CONFIG_FILE = "devices.yaml"
PING_COUNT = 1
PING_TIMEOUT = 2
CHECK_INTERVAL = 30

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename="sync_status.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------- HELPERS ----------------
def ping(ip, bind_ip=None):
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

def add_block(src_ip, dst_ip):
    cmd = ["iptables", "-A", "FORWARD", "-s", src_ip, "-d", dst_ip, "-j", "DROP"]
    subprocess.run(cmd, stderr=subprocess.DEVNULL)
    logging.info(f"Blocked connection {src_ip} -> {dst_ip}")

def remove_block(src_ip, dst_ip):
    cmd = ["iptables", "-D", "FORWARD", "-s", src_ip, "-d", dst_ip, "-j", "DROP"]
    subprocess.run(cmd, stderr=subprocess.DEVNULL)
    logging.info(f"Unblocked connection {src_ip} -> {dst_ip}")

# ---------------- STATE ----------------
last_status = {}           # device -> up/down
conn_blocked = {}          # (src, dst) -> bool
conn_blocked_since = {}    # (src, dst) -> timestamp

# ---------------- MQTT CALLBACKS ----------------
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        topic_parts = msg.topic.split("/")
        # Expected: health/<device>/<peer>
        if len(topic_parts) < 3:
            return
        dev, peer = topic_parts[1], topic_parts[2]
        status = data.get("status")
        ts = data.get("time")
        logging.info(f"MQTT health report: {dev}->{peer} {status} at {ts}")
        userdata["reports"].append((dev, peer, status))
    except Exception as e:
        logging.error(f"MQTT parse error: {e}")

# ---------------- MAIN ----------------
def main():
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)

    gns3_cfg = config["gns3"]
    project_id = gns3_cfg["project_id"]
    devices_phys = config["devices"]["physical"]
    devices_digi = config["devices"]["digital"]
    monitor_cfg = config.get("monitor", {})

    FAIL_THRESHOLD = monitor_cfg.get("fail_threshold", 3)
    RECOVER_THRESHOLD = monitor_cfg.get("recover_threshold", 3)
    CONN_FAIL_THRESHOLD = monitor_cfg.get("connection_fail_threshold", 3)
    CONN_RECOVER_THRESHOLD = monitor_cfg.get("connection_recover_threshold", 3)
    CONN_MIN_BLOCK_SECONDS = monitor_cfg.get("connection_min_block_seconds", 30)

    # MQTT setup
    reports = []
    mqtt_cfg = config["mqtt"]
    client = mqtt.Client(userdata={"reports": reports})
    client.username_pw_set(mqtt_cfg["user"], mqtt_cfg["password"])
    client.on_message = on_message
    client.connect(mqtt_cfg["host"], mqtt_cfg.get("port", 1883), 60)
    client.subscribe("health/#")
    threading.Thread(target=client.loop_forever, daemon=True).start()

    logging.info("=== Sync agent started ===")

    fail_counts = {name: 0 for name in devices_phys}
    success_counts = {name: 0 for name in devices_phys}

    while True:
        # ---- device liveness check ----
        for name, phys in devices_phys.items():
            ip = phys["ip"]
            bind_ip = phys.get("bind_ip")
            is_up = ping(ip, bind_ip)
            logging.info(f"Ping {name} ({ip}) via {bind_ip}: {'UP' if is_up else 'DOWN'}")

            prev = last_status.get(name, True)
            if is_up:
                fail_counts[name] = 0
                success_counts[name] += 1
            else:
                success_counts[name] = 0
                fail_counts[name] += 1

            changed = False
            if not is_up and prev and fail_counts[name] >= FAIL_THRESHOLD:
                last_status[name] = False
                changed = True
            if is_up and not prev and success_counts[name] >= RECOVER_THRESHOLD:
                last_status[name] = True
                changed = True

            digi = devices_digi.get(name)
            if digi and changed:
                node_id = digi.get("gns3_node_id")
                if not node_id:
                    continue
                if last_status[name]:
                    start_node(gns3_cfg, project_id, node_id)
                else:
                    stop_node(gns3_cfg, project_id, node_id)

        # ---- connection-level health (from MQTT reports) ----
        while reports:
            dev, peer, status = reports.pop(0)
            phys_src = devices_phys.get(dev)
            phys_dst = devices_phys.get(peer)
            digi_src = devices_digi.get(dev)
            digi_dst = devices_digi.get(peer)
            if not (phys_src and phys_dst and digi_src and digi_dst):
                continue

            sip, dip = digi_src["ip"], digi_dst["ip"]
            key = (dev, peer)
            now = time.time()

            # Handle DOWN
            if status == "DOWN":
                if not conn_blocked.get(key, False):
                    add_block(sip, dip)
                    conn_blocked[key] = True
                    conn_blocked_since[key] = now
                    logging.info(f"Connection {dev}->{peer} marked DOWN and blocked")

            # Handle UP with thresholds
            elif status == "UP":
                blocked_since = conn_blocked_since.get(key, 0)
                blocked_age = now - blocked_since if blocked_since else 9999
                if conn_blocked.get(key, False) and (
                    blocked_age >= CONN_MIN_BLOCK_SECONDS
                ):
                    remove_block(sip, dip)
                    conn_blocked[key] = False
                    conn_blocked_since.pop(key, None)
                    logging.info(f"Connection {dev}->{peer} marked UP and unblocked (age {blocked_age:.1f}s)")

        # Safety check: hold blocks until timeout
        now = time.time()
        for key, since in list(conn_blocked_since.items()):
            age = now - since
            if age >= CONN_MIN_BLOCK_SECONDS and conn_blocked.get(key, False):
                dev, peer = key
                digi_src = devices_digi.get(dev)
                digi_dst = devices_digi.get(peer)
                if digi_src and digi_dst:
                    sip, dip = digi_src["ip"], digi_dst["ip"]
                    remove_block(sip, dip)
                    conn_blocked[key] = False
                    conn_blocked_since.pop(key, None)
                    logging.info(f"Connection {dev}->{peer} auto-unblocked after {age:.1f}s timeout")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
