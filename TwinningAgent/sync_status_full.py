#!/usr/bin/env python3
"""
sync_status_full.py

Proxy master:
- Pings physical devices → stop/start digital nodes via GNS3 API
- Subscribes to device-side health reports (MQTT topic: <mqtt_prefix>/<src>/<dst>)
- Blocks/unblocks digital-side connections (iptables) when device-reported connections fail
- Falls back to suspending GNS3 links between digital nodes if iptables isn't sufficient
- Proxy is authoritative: if proxy can't reach a device, it is considered DOWN and overrides connection reports.

Reads monitoring thresholds and MQTT settings from devices.yaml under `monitor` and `mqtt`.
"""

import os
import time
import json
import yaml
import logging
import subprocess
import signal
import sys
from typing import Dict, Tuple, List, Optional

import requests
from requests.auth import HTTPBasicAuth
import paho.mqtt.client as mqtt
import argparse

# ---------------- DEFAULTS ----------------
DEFAULT_CONFIG_FILE = "devices.yaml"

DEFAULTS = {
    "PING_COUNT": 1,
    "PING_TIMEOUT": 2,
    "CHECK_INTERVAL": 10,
    "DEVICE_FAIL_THRESHOLD": 3,
    "DEVICE_RECOVER_THRESHOLD": 3,
    "CONN_FAIL_THRESHOLD": 1,
    "CONN_RECOVER_THRESHOLD": 1,
    "IPTABLES_CHAIN": "FORWARD",
    "MQTT_CLIENT_ID": "proxy-sync-agent",
    "MQTT_KEEPALIVE": 60,
}

# ---------------- LOGGING ----------------
LOGFILE = "sync_status_full.log"
logging.basicConfig(
    filename=LOGFILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# ---------------- GLOBALS ----------------
cfg = None  # loaded YAML config

# runtime params
PING_COUNT = DEFAULTS["PING_COUNT"]
PING_TIMEOUT = DEFAULTS["PING_TIMEOUT"]
CHECK_INTERVAL = DEFAULTS["CHECK_INTERVAL"]
DEVICE_FAIL_THRESHOLD = DEFAULTS["DEVICE_FAIL_THRESHOLD"]
DEVICE_RECOVER_THRESHOLD = DEFAULTS["DEVICE_RECOVER_THRESHOLD"]
CONN_FAIL_THRESHOLD = DEFAULTS["CONN_FAIL_THRESHOLD"]
CONN_RECOVER_THRESHOLD = DEFAULTS["CONN_RECOVER_THRESHOLD"]
IPTABLES_CHAIN = DEFAULTS["IPTABLES_CHAIN"]
MQTT_CLIENT_ID = DEFAULTS["MQTT_CLIENT_ID"]
MQTT_KEEPALIVE = DEFAULTS["MQTT_KEEPALIVE"]

# states / counters
device_fail_counts: Dict[str,int] = {}
device_success_counts: Dict[str,int] = {}
device_status: Dict[str,bool] = {}   # True=UP, False=DOWN

conn_fail_counts: Dict[Tuple[str,str],int] = {}
conn_success_counts: Dict[Tuple[str,str],int] = {}
conn_reported_status: Dict[Tuple[str,str],bool] = {}

# Which connection pairs are currently blocked by iptables
conn_blocked: Dict[Tuple[str,str],bool] = {}

# Which connection pairs have suspended GNS3 links (list of link_ids)
conn_blocked_links: Dict[Tuple[str,str], List[str]] = {}

# Cache of gns3 node running state
gns3_node_running: Dict[str,bool] = {}

# MQTT client handle
mqtt_client: Optional[mqtt.Client] = None

# expected connections map derived from YAML
expected_connections: Dict[str, List[str]] = {}

# dry-run flag (don’t change iptables or gns3 if True)
DRY_RUN = False

# graceful shutdown
_running = True

# ---------------- CONFIG LOADING ----------------
def load_config(path: str):
    global cfg, PING_COUNT, PING_TIMEOUT, CHECK_INTERVAL
    global DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD
    global CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD
    global IPTABLES_CHAIN, MQTT_CLIENT_ID, MQTT_KEEPALIVE
    global expected_connections

    with open(path) as f:
        cfg = yaml.safe_load(f)

    logging.info("Loaded config from %s", path)

    monitor_cfg = cfg.get("monitor", {})

    def _get_int(k, default):
        v = monitor_cfg.get(k)
        try:
            return int(v) if v is not None else default
        except Exception:
            return default

    CHECK_INTERVAL = _get_int("check_interval_seconds", DEFAULTS["CHECK_INTERVAL"])
    DEVICE_FAIL_THRESHOLD = _get_int("device_fail_threshold", DEFAULTS["DEVICE_FAIL_THRESHOLD"])
    DEVICE_RECOVER_THRESHOLD = _get_int("device_recover_threshold", DEFAULTS["DEVICE_RECOVER_THRESHOLD"])
    CONN_FAIL_THRESHOLD = _get_int("connection_fail_threshold", DEFAULTS["CONN_FAIL_THRESHOLD"])
    CONN_RECOVER_THRESHOLD = _get_int("connection_recover_threshold", DEFAULTS["CONN_RECOVER_THRESHOLD"])
    IPTABLES_CHAIN = monitor_cfg.get("iptables_chain", DEFAULTS["IPTABLES_CHAIN"]) or DEFAULTS["IPTABLES_CHAIN"]

    PING_COUNT = int(monitor_cfg.get("ping_count", DEFAULTS["PING_COUNT"]))
    PING_TIMEOUT = int(monitor_cfg.get("ping_timeout", DEFAULTS["PING_TIMEOUT"]))

    mqtt_cfg = cfg.get("mqtt", {})
    MQTT_CLIENT_ID = mqtt_cfg.get("client_id", DEFAULTS["MQTT_CLIENT_ID"])
    MQTT_KEEPALIVE = int(mqtt_cfg.get("keepalive", DEFAULTS["MQTT_KEEPALIVE"]))

    # build expected connections dynamically from YAML physical devices 'connections' fields
    phys = cfg.get("devices", {}).get("physical", {})
    expected_connections = {}
    for name, info in phys.items():
        conns = info.get("connections")
        expected_connections[name] = conns[:] if isinstance(conns, list) else []

    # fallback mapping if YAML did not specify any
    if not any(expected_connections.values()):
        expected_connections = {
            "broker": ["sensor", "ipcam"],
            "router": ["broker", "ipcam", "sensor"],
            "sensor": ["broker", "router"],
            "ipcam": []
        }

    logging.info("Runtime params: CHECK_INTERVAL=%s, DEVICE_FAIL_THRESHOLD=%s, DEVICE_RECOVER_THRESHOLD=%s, CONN_FAIL_THRESHOLD=%s, CONN_RECOVER_THRESHOLD=%s, IPTABLES_CHAIN=%s",
                 CHECK_INTERVAL, DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD, CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD, IPTABLES_CHAIN)
    logging.info("Expected connections: %s", expected_connections)

# ---------------- PING HELPER ----------------
def ping(ip: str, bind_ip: Optional[str] = None) -> bool:
    """Ping IP from proxy (optionally binding source)."""
    try:
        cmd = ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT)]
        if bind_ip:
            cmd.extend(["-I", bind_ip])
        cmd.append(str(ip))
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception as e:
        logging.exception("Ping error: %s", e)
        return False

# ---------------- GNS3 API helpers ----------------
def gns3_request(method: str, endpoint: str, data=None):
    """Generic GNS3 API request. Returns requests.Response or None."""
    try:
        g = cfg["gns3"]
        base = g["url"].rstrip("/")
        url = f"{base}{endpoint}"
        r = requests.request(method, url, auth=HTTPBasicAuth(g["user"], g["password"]), timeout=8, json=data)
        if not r.ok:
            logging.warning("GNS3 API %s %s -> %s : %s", method, url, r.status_code, r.text)
        return r
    except Exception as e:
        logging.exception("GNS3 API request error: %s", e)
        return None

def start_node(node_id: str) -> bool:
    if DRY_RUN:
        logging.info("[dry-run] start_node %s", node_id)
        gns3_node_running[node_id] = True
        return True
    project = cfg["gns3"]["project_id"]
    logging.info("Starting node %s", node_id)
    r = gns3_request("POST", f"/projects/{project}/nodes/{node_id}/start")
    if r is not None and r.ok:
        gns3_node_running[node_id] = True
        return True
    return False

def stop_node(node_id: str) -> bool:
    if DRY_RUN:
        logging.info("[dry-run] stop_node %s", node_id)
        gns3_node_running[node_id] = False
        return True
    project = cfg["gns3"]["project_id"]
    logging.info("Stopping node %s", node_id)
    r = gns3_request("POST", f"/projects/{project}/nodes/{node_id}/stop")
    if r is not None and r.ok:
        gns3_node_running[node_id] = False
        return True
    return False

def check_node_state(node_id: str) -> bool:
    if DRY_RUN:
        return gns3_node_running.get(node_id, False)
    project = cfg["gns3"]["project_id"]
    r = gns3_request("GET", f"/projects/{project}/nodes/{node_id}")
    if r is None or not r.ok:
        return False
    data = r.json()
    state = data.get("status") == "started"
    gns3_node_running[node_id] = state
    return state

# ---------------- GNS3 link helpers ----------------
def find_links_between_node_ids(node_a_id: str, node_b_id: str) -> List[str]:
    """Return link_id list connecting node_a_id <> node_b_id."""
    if DRY_RUN:
        logging.info("[dry-run] find_links_between_node_ids %s %s", node_a_id, node_b_id)
        return []
    project = cfg["gns3"]["project_id"]
    r = gns3_request("GET", f"/projects/{project}/links")
    if r is None or not r.ok:
        logging.warning("Could not query GNS3 links")
        return []
    links = r.json()
    found: List[str] = []
    for L in links:
        nodes = L.get("nodes", [])
        ids = [n.get("node_id") for n in nodes if n.get("node_id")]
        if node_a_id in ids and node_b_id in ids:
            # GNS3 API uses 'link_id' or 'id' depending on version — check both
            lid = L.get("link_id") or L.get("id") or L.get("uuid")
            if lid:
                found.append(lid)
    return found

def suspend_link(link_id: str, suspend: bool = True) -> bool:
    """Set link suspend state via GNS3 API patch. Returns True on success."""
    if DRY_RUN:
        logging.info("[dry-run] suspend_link %s => %s", link_id, suspend)
        return True
    project = cfg["gns3"]["project_id"]
    logging.info("Setting link %s suspend=%s", link_id, suspend)
    r = gns3_request("PATCH", f"/projects/{project}/links/{link_id}", data={"suspend": bool(suspend)})
    if r is None:
        logging.warning("GNS3 link suspend request failed for %s", link_id)
        return False
    if r.ok:
        logging.info("Link %s suspend=%s succeeded", link_id, suspend)
        return True
    logging.warning("Link suspend returned %s : %s", r.status_code, r.text)
    return False

# ---------------- iptables helpers ----------------
def iptables_rule_exists(src_ip: str, dst_ip: str) -> bool:
    if DRY_RUN:
        logging.info("[dry-run] iptables_rule_exists %s -> %s", src_ip, dst_ip)
        return False
    cmd = ["iptables", "-C", IPTABLES_CHAIN, "-s", src_ip, "-d", dst_ip, "-j", "DROP"]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False

def add_block(src_ip: str, dst_ip: str):
    if DRY_RUN:
        logging.info("[dry-run] add_block %s -> %s", src_ip, dst_ip)
        return
    try:
        if not iptables_rule_exists(src_ip, dst_ip):
            subprocess.check_call(["iptables", "-A", IPTABLES_CHAIN, "-s", src_ip, "-d", dst_ip, "-j", "DROP"])
            logging.info("Added iptables block %s -> %s", src_ip, dst_ip)
        if not iptables_rule_exists(dst_ip, src_ip):
            subprocess.check_call(["iptables", "-A", IPTABLES_CHAIN, "-s", dst_ip, "-d", src_ip, "-j", "DROP"])
            logging.info("Added iptables block %s -> %s", dst_ip, src_ip)
    except subprocess.CalledProcessError as e:
        logging.exception("Failed to add iptables rule: %s", e)

def remove_block(src_ip: str, dst_ip: str):
    if DRY_RUN:
        logging.info("[dry-run] remove_block %s -> %s", src_ip, dst_ip)
        return
    try:
        while iptables_rule_exists(src_ip, dst_ip):
            subprocess.check_call(["iptables", "-D", IPTABLES_CHAIN, "-s", src_ip, "-d", dst_ip, "-j", "DROP"])
            logging.info("Removed iptables block %s -> %s", src_ip, dst_ip)
        while iptables_rule_exists(dst_ip, src_ip):
            subprocess.check_call(["iptables", "-D", IPTABLES_CHAIN, "-s", dst_ip, "-d", src_ip, "-j", "DROP"])
            logging.info("Removed iptables block %s -> %s", dst_ip, src_ip)
    except subprocess.CalledProcessError as e:
        logging.exception("Failed to remove iptables rule: %s", e)

# ---------------- MQTT callbacks ----------------
def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    logging.info("Connected to MQTT broker (reason=%s) -- subscribing to prefix", reason_code)
    prefix = cfg.get("monitor", {}).get("mqtt_prefix", "health")
    client.subscribe(f"{prefix}/#")
    logging.info("Subscribed to %s/#", prefix)

def on_mqtt_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")
        if len(topic_parts) < 3:
            return
        prefix, src, dst = topic_parts[:3]
        payload = msg.payload.decode().strip()
        status = None
        try:
            js = json.loads(payload)
            status = js.get("status") or js.get("state") or js.get("status_text")
        except Exception:
            status = payload

        status = str(status).upper()
        key = (src, dst)

        if status == "DOWN":
            conn_fail_counts[key] = conn_fail_counts.get(key, 0) + 1
            conn_success_counts[key] = 0
        elif status == "UP":
            conn_success_counts[key] = conn_success_counts.get(key, 0) + 1
            conn_fail_counts[key] = 0
        else:
            return

        prev_reported = conn_reported_status.get(key, True)
        if conn_fail_counts.get(key, 0) >= CONN_FAIL_THRESHOLD and prev_reported:
            conn_reported_status[key] = False
            logging.info("Reported connection DOWN from device: %s -> %s", src, dst)
        if conn_success_counts.get(key, 0) >= CONN_RECOVER_THRESHOLD and not prev_reported:
            conn_reported_status[key] = True
            logging.info("Reported connection UP from device: %s -> %s", src, dst)
    except Exception as e:
        logging.exception("Error processing MQTT message %s: %s", msg.topic, e)

# ---------------- CORE PROCESSING ----------------
def process_device_checks():
    phys = cfg["devices"]["physical"]
    digi = cfg["devices"]["digital"]

    for name, info in phys.items():
        ip = info["ip"]
        bind_ip = info.get("bind_ip")
        alive = ping(ip, bind_ip)

        if not alive:
            device_fail_counts[name] = device_fail_counts.get(name, 0) + 1
            device_success_counts[name] = 0
        else:
            device_success_counts[name] = device_success_counts.get(name, 0) + 1
            device_fail_counts[name] = 0

        prev = device_status.get(name, None)

        # DECLARE DOWN
        if device_fail_counts.get(name, 0) >= DEVICE_FAIL_THRESHOLD:
            if prev is None or prev is True:
                device_status[name] = False
                logging.warning("Device %s declared DOWN by proxy (after %d fails)", name, device_fail_counts[name])

                # stop digital node if configured
                if name in digi and digi[name].get("gns3_node_id"):
                    nid = digi[name]["gns3_node_id"]
                    stop_node(nid)

                # block digital device's connectivity to others
                digi_ip = digi.get(name, {}).get("ip")
                if digi_ip:
                    for other_name, other_info in digi.items():
                        if other_name == name:
                            continue
                        other_ip = other_info.get("ip")
                        if other_ip:
                            add_block(digi_ip, other_ip)
                            conn_blocked[(name, other_name)] = True
                            conn_blocked[(other_name, name)] = True
                            logging.info("Proxy authoritative: blocked digital %s -> %s due to %s DOWN", name, other_name, name)

                    # also attempt to suspend any GNS3 links between this node and others
                    node_a = digi.get(name, {}).get("gns3_node_id")
                    if node_a:
                        for other_name, other_info in digi.items():
                            if other_name == name:
                                continue
                            node_b = other_info.get("gns3_node_id")
                            if node_b:
                                lids = find_links_between_node_ids(node_a, node_b)
                                if lids:
                                    blocked = []
                                    for lid in lids:
                                        if suspend_link(lid, True):
                                            blocked.append(lid)
                                    if blocked:
                                        conn_blocked_links[(name, other_name)] = blocked
                                        conn_blocked_links[(other_name, name)] = blocked
                                        logging.info("Suspended GNS3 links for %s <-> %s : %s", name, other_name, blocked)

        # DECLARE RECOVERED
        if device_success_counts.get(name, 0) >= DEVICE_RECOVER_THRESHOLD:
            if prev is None or prev is False:
                device_status[name] = True
                logging.info("Device %s recovered (after %d successes)", name, device_success_counts[name])
                if name in digi and digi[name].get("gns3_node_id"):
                    start_node(digi[name]["gns3_node_id"])

                # remove any blocks for digital device
                digi_ip = digi.get(name, {}).get("ip")
                if digi_ip:
                    for other_name, other_info in digi.items():
                        if other_name == name:
                            continue
                        other_ip = other_info.get("ip")
                        if other_ip and conn_blocked.get((name, other_name), False):
                            remove_block(digi_ip, other_ip)
                            conn_blocked[(name, other_name)] = False
                            conn_blocked[(other_name, name)] = False
                            logging.info("Proxy authoritative: unblocked digital %s <-> %s after %s recovered", name, other_name, name)

                    # unsuspend GNS3 links if we suspended earlier
                    node_a = digi.get(name, {}).get("gns3_node_id")
                    if node_a:
                        for other_name, other_info in digi.items():
                            if other_name == name:
                                continue
                            key = (name, other_name)
                            if key in conn_blocked_links:
                                lids = conn_blocked_links.get(key, [])
                                for lid in lids:
                                    suspend_link(lid, False)
                                    logging.info("Unsuspended GNS3 link %s for %s<->%s", lid, name, other_name)
                                # cleanup both directions
                                conn_blocked_links.pop((name, other_name), None)
                                conn_blocked_links.pop((other_name, name), None)

def process_connection_reports():
    phys = cfg["devices"]["physical"]
    digi = cfg["devices"]["digital"]

    # expected_connections drives which pairs we care about
    for src, targets in expected_connections.items():
        for dst in targets:
            key = (src, dst)
            reported_up = conn_reported_status.get(key, True)
            src_up = device_status.get(src, True)
            dst_up = device_status.get(dst, True)

            # If either device is proxy-declared DOWN → enforce blocks on digital side
            if not src_up or not dst_up:
                if src in digi and dst in digi:
                    sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                    if not conn_blocked.get((src, dst), False):
                        add_block(sip, dip)
                        conn_blocked[(src, dst)] = True
                        conn_blocked[(dst, src)] = True
                        logging.info("Blocking digital connection %s->%s due to physical DOWN (proxy authoritative)", src, dst)

                    # try suspend gns3 links if node ids present
                    node_a = digi[src].get("gns3_node_id")
                    node_b = digi[dst].get("gns3_node_id")
                    if node_a and node_b and (src, dst) not in conn_blocked_links:
                        lids = find_links_between_node_ids(node_a, node_b)
                        if lids:
                            blk = []
                            for lid in lids:
                                if suspend_link(lid, True):
                                    blk.append(lid)
                            if blk:
                                conn_blocked_links[(src, dst)] = blk
                                conn_blocked_links[(dst, src)] = blk
                                logging.info("Suspended GNS3 links for %s<->%s : %s", src, dst, blk)
                continue

            # If device-reported connection DOWN → block digital pair
            if not reported_up:
                if src in digi and dst in digi and not conn_blocked.get((src, dst), False):
                    sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                    add_block(sip, dip)
                    conn_blocked[(src, dst)] = True
                    conn_blocked[(dst, src)] = True
                    logging.info("Blocking digital connection %s->%s (reported by device)", src, dst)

                    # suspend links if available
                    node_a = digi[src].get("gns3_node_id")
                    node_b = digi[dst].get("gns3_node_id")
                    if node_a and node_b:
                        lids = find_links_between_node_ids(node_a, node_b)
                        if lids:
                            blk = []
                            for lid in lids:
                                if suspend_link(lid, True):
                                    blk.append(lid)
                            if blk:
                                conn_blocked_links[(src, dst)] = blk
                                conn_blocked_links[(dst, src)] = blk
                                logging.info("Suspended GNS3 links for %s<->%s : %s", src, dst, blk)
            else:
                # reported_up True => un-block if previously blocked by report
                if conn_blocked.get((src, dst), False):
                    if src in digi and dst in digi:
                        sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                        remove_block(sip, dip)
                        conn_blocked[(src, dst)] = False
                        conn_blocked[(dst, src)] = False
                        logging.info("Unblocked digital connection %s<->%s (reported recovered)", src, dst)

                    # unsuspend any links we suspended
                    if (src, dst) in conn_blocked_links:
                        lids = conn_blocked_links.pop((src, dst), [])
                        conn_blocked_links.pop((dst, src), None)
                        for lid in lids:
                            suspend_link(lid, False)
                            logging.info("Unsuspended GNS3 link %s for %s<->%s", lid, src, dst)

# ---------------- MAIN LOOP ----------------
def main_loop():
    global _running
    logging.info("Starting proxy sync main loop")

    phys_names = list(cfg["devices"]["physical"].keys())
    for name in phys_names:
        device_fail_counts[name] = 0
        device_success_counts[name] = 0
        device_status[name] = True

    # initialize connection counters from expected_connections
    for s, targets in expected_connections.items():
        for t in targets:
            key = (s, t)
            conn_fail_counts[key] = 0
            conn_success_counts[key] = 0
            conn_reported_status[key] = True
            conn_blocked[key] = False

    while _running:
        try:
            process_device_checks()
            process_connection_reports()
        except Exception as e:
            logging.exception("Error in main loop iteration: %s", e)
        time.sleep(CHECK_INTERVAL)

# ---------------- MQTT RUNNER ----------------
def start_mqtt_listener():
    global mqtt_client
    broker_ip = cfg.get("mqtt", {}).get("host") or cfg["devices"]["physical"]["broker"]["ip"]
    broker_port = int(cfg.get("mqtt", {}).get("port", 1883))

    mqtt_client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message

    user = cfg.get("mqtt", {}).get("user")
    pwd = cfg.get("mqtt", {}).get("password")
    if user and pwd:
        mqtt_client.username_pw_set(user, pwd)

    try:
        mqtt_client.connect(broker_ip, broker_port, MQTT_KEEPALIVE)
    except Exception as e:
        logging.exception("MQTT connect failed: %s", e)
    mqtt_client.loop_start()

# ---------------- SHUTDOWN ----------------
def shutdown(signum=None, frame=None):
    global _running
    logging.info("Shutdown signal received")
    _running = False
    try:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
    except Exception:
        pass
    sys.exit(0)

# ---------------- CLI / ENTRYPOINT ----------------
def parse_args():
    p = argparse.ArgumentParser(description="Proxy sync agent (sync_status_full.py)")
    p.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="devices.yaml path")
    p.add_argument("--dry-run", action="store_true", help="Do not change iptables / GNS3, just log actions")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    DRY_RUN = args.dry_run
    try:
        load_config(args.config)
    except Exception as e:
        print("Failed to load config:", e)
        sys.exit(2)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    start_mqtt_listener()
    logging.info("sync_status_full started (dry_run=%s). Watching devices: %s", DRY_RUN, list(cfg["devices"]["physical"].keys()))
    try:
        main_loop()
    except Exception as e:
        logging.exception("Fatal error: %s", e)
        shutdown()

