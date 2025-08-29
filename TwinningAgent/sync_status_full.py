#!/usr/bin/env python3
"""
sync_status_full.py (updated)
- Explicit MQTT client API version (MQTTv311 + callback API v2)
- Uses YAML `connections` per-device to build expected connection matrix
- Initializes counters dynamically from YAML
"""

import os
import time
import json
import yaml
import logging
import subprocess
import signal
import sys
from typing import Dict, Tuple

import requests
from requests.auth import HTTPBasicAuth
import paho.mqtt.client as mqtt

# ---------------- CONFIG FILE ----------------
CONFIG_FILE = "devices.yaml"

# ---------------- DEFAULTS (will be overridden by YAML monitor block) ----------------
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
logging.basicConfig(
    filename="sync_status_full.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------- GLOBAL STATE ----------------
cfg = None  # full YAML config

# Effective runtime parameters (populated after loading YAML)
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

# device_name -> dict { ip, bind_ip, ... }
device_fail_counts: Dict[str,int] = {}
device_success_counts: Dict[str,int] = {}
device_status: Dict[str,bool] = {}   # True=UP, False=DOWN

# connection reported state and counters
conn_fail_counts: Dict[Tuple[str,str],int] = {}
conn_success_counts: Dict[Tuple[str,str],int] = {}
conn_reported_status: Dict[Tuple[str,str],bool] = {}  # latest reported by devices (True=UP)

# digital-side block state (to avoid duplicate iptables ops)
conn_blocked: Dict[Tuple[str,str],bool] = {}

# GNS3 node running cache
gns3_node_running: Dict[str,bool] = {}

# MQTT client (initialized later)
mqtt_client = None

# expected mapping (built dynamically from YAML)
expected_connections: Dict[str, list] = {}

# Graceful shutdown flag
_running = True

# ---------------- HELPERS ----------------
def load_config(path=CONFIG_FILE):
    """Load YAML and apply monitor/mqtt overrides to runtime variables."""
    global cfg, PING_COUNT, PING_TIMEOUT, CHECK_INTERVAL
    global DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD
    global CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD
    global IPTABLES_CHAIN, MQTT_CLIENT_ID, MQTT_KEEPALIVE
    global expected_connections

    with open(path) as f:
        cfg = yaml.safe_load(f)

    logging.info("Loaded config from %s", path)

    monitor_cfg = cfg.get("monitor", {})
    # Safely parse integers with defaults
    def _get_int(key, default):
        v = monitor_cfg.get(key)
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

    # Ping params (top-level constants - optional to expose)
    PING_COUNT = int(monitor_cfg.get("ping_count", DEFAULTS["PING_COUNT"]))
    PING_TIMEOUT = int(monitor_cfg.get("ping_timeout", DEFAULTS["PING_TIMEOUT"]))

    mqtt_cfg = cfg.get("mqtt", {})
    MQTT_CLIENT_ID = mqtt_cfg.get("client_id", DEFAULTS["MQTT_CLIENT_ID"])
    MQTT_KEEPALIVE = int(mqtt_cfg.get("keepalive", DEFAULTS["MQTT_KEEPALIVE"]))

    # build expected connections from YAML `devices.physical[*].connections`
    expected_connections = {}
    phys = cfg.get("devices", {}).get("physical", {})
    for name, info in phys.items():
        conns = info.get("connections")
        if isinstance(conns, list):
            expected_connections[name] = conns[:]
        else:
            expected_connections[name] = []

    # fallback (if empty) - keep the previous default mapping
    if not any(expected_connections.values()):
        expected_connections = {
            "broker": ["sensor", "ipcam"],
            "router": ["broker", "ipcam", "sensor"],
            "sensor": ["broker", "router"],
            "ipcam": []
        }

    logging.info(
        "Runtime params: CHECK_INTERVAL=%s, DEVICE_FAIL_THRESHOLD=%s, DEVICE_RECOVER_THRESHOLD=%s, CONN_FAIL_THRESHOLD=%s, CONN_RECOVER_THRESHOLD=%s, IPTABLES_CHAIN=%s",
        CHECK_INTERVAL, DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD, CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD, IPTABLES_CHAIN
    )
    logging.info("Expected connections: %s", expected_connections)

def ping(ip: str, bind_ip: str = None) -> bool:
    """Ping an IP using the system ping command. Returns True if reachable."""
    try:
        cmd = ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT)]
        if bind_ip:
            cmd.extend(["-I", bind_ip])
        cmd.append(str(ip))
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception as e:
        logging.exception("Ping command error: %s", e)
        return False

def gns3_request(method: str, endpoint: str, data=None):
    """Call GNS3 API using credentials in cfg['gns3']."""
    g = cfg["gns3"]
    base = g["url"].rstrip("/")
    url = f"{base}{endpoint}"
    try:
        r = requests.request(method, url, auth=HTTPBasicAuth(g["user"], g["password"]), timeout=8, json=data)
        if not r.ok:
            logging.warning("GNS3 API %s %s returned %s: %s", method, url, r.status_code, r.text)
        return r
    except Exception as e:
        logging.exception("GNS3 API request error: %s", e)
        return None

def start_node(node_id: str):
    project = cfg["gns3"]["project_id"]
    logging.info("Starting node %s", node_id)
    r = gns3_request("POST", f"/projects/{project}/nodes/{node_id}/start")
    if r is not None and r.ok:
        gns3_node_running[node_id] = True
        return True
    return False

def stop_node(node_id: str):
    project = cfg["gns3"]["project_id"]
    logging.info("Stopping node %s", node_id)
    r = gns3_request("POST", f"/projects/{project}/nodes/{node_id}/stop")
    if r is not None and r.ok:
        gns3_node_running[node_id] = False
        return True
    return False

def check_node_state(node_id: str):
    project = cfg["gns3"]["project_id"]
    r = gns3_request("GET", f"/projects/{project}/nodes/{node_id}")
    if r is None or not r.ok:
        return False
    data = r.json()
    state = data.get("status") == "started"
    gns3_node_running[node_id] = state
    return state

# ---------------- iptables helpers ----------------
def iptables_rule_exists(src_ip: str, dst_ip: str) -> bool:
    cmd = ["iptables", "-C", IPTABLES_CHAIN, "-s", src_ip, "-d", dst_ip, "-j", "DROP"]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False

def add_block(src_ip: str, dst_ip: str):
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
    try:
        while iptables_rule_exists(src_ip, dst_ip):
            subprocess.check_call(["iptables", "-D", IPTABLES_CHAIN, "-s", src_ip, "-d", dst_ip, "-j", "DROP"])
            logging.info("Removed iptables block %s -> %s", src_ip, dst_ip)
        while iptables_rule_exists(dst_ip, src_ip):
            subprocess.check_call(["iptables", "-D", IPTABLES_CHAIN, "-s", dst_ip, "-d", src_ip, "-j", "DROP"])
            logging.info("Removed iptables block %s -> %s", dst_ip, src_ip)
    except subprocess.CalledProcessError as e:
        logging.exception("Failed to remove iptables rule: %s", e)

# ---------------- MQTT handling for device reports ----------------
def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    logging.info("Connected to MQTT broker (reason=%s) -- subscribing to health/#", reason_code)
    prefix = cfg.get("monitor", {}).get("mqtt_prefix", "health")
    client.subscribe(f"{prefix}/#")

def on_mqtt_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")
        if len(topic_parts) < 3:
            return
        _, src, dst = topic_parts[:3]
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
        if conn_fail_counts.get(key,0) >= CONN_FAIL_THRESHOLD and prev_reported:
            conn_reported_status[key] = False
            logging.info("Reported connection DOWN from device: %s -> %s", src, dst)
        if conn_success_counts.get(key,0) >= CONN_RECOVER_THRESHOLD and not prev_reported:
            conn_reported_status[key] = True
            logging.info("Reported connection UP from device: %s -> %s", src, dst)
    except Exception as e:
        logging.exception("Error processing MQTT message %s: %s", msg.topic, e)

# ---------------- Main decision logic ----------------
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

        if device_fail_counts.get(name,0) >= DEVICE_FAIL_THRESHOLD:
            if prev is None or prev is True:
                device_status[name] = False
                logging.warning("Device %s declared DOWN by proxy (after %d fails)", name, device_fail_counts[name])
                if name in digi and digi[name].get("gns3_node_id"):
                    stop_node(digi[name]["gns3_node_id"])

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

        if device_success_counts.get(name,0) >= DEVICE_RECOVER_THRESHOLD:
            if prev is None or prev is False:
                device_status[name] = True
                logging.info("Device %s recovered (after %d successes)", name, device_success_counts[name])
                if name in digi and digi[name].get("gns3_node_id"):
                    start_node(digi[name]["gns3_node_id"])
                digi_ip = digi.get(name, {}).get("ip")
                if digi_ip:
                    for other_name, other_info in digi.items():
                        if other_name == name:
                            continue
                        other_ip = other_info.get("ip")
                        if other_ip:
                            if conn_blocked.get((name, other_name), False):
                                remove_block(digi_ip, other_ip)
                                conn_blocked[(name, other_name)] = False
                                conn_blocked[(other_name, name)] = False

def process_connection_reports():
    phys = cfg["devices"]["physical"]
    digi = cfg["devices"]["digital"]

    # Use expected_connections derived from YAML (built in load_config)
    for src, targets in expected_connections.items():
        for dst in targets:
            key = (src, dst)
            reported_up = conn_reported_status.get(key, True)
            src_up = device_status.get(src, True)
            dst_up = device_status.get(dst, True)
            if not src_up or not dst_up:
                # proxy authoritative: if physical src/dst down, block digital pair
                if src in digi and dst in digi:
                    sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                    if not conn_blocked.get((src,dst), False):
                        add_block(sip, dip)
                        conn_blocked[(src,dst)] = True
                        conn_blocked[(dst,src)] = True
                        logging.info("Blocking digital connection %s->%s due to device DOWN (proxy authoritative)", src, dst)
                continue

            if not reported_up:
                if src in digi and dst in digi and not conn_blocked.get((src,dst), False):
                    sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                    add_block(sip, dip)
                    conn_blocked[(src,dst)] = True
                    conn_blocked[(dst,src)] = True
                    logging.info("Blocking digital connection %s->%s (reported by device)", src, dst)
            else:
                if conn_blocked.get((src,dst), False):
                    if src in digi and dst in digi:
                        sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                        remove_block(sip, dip)
                        conn_blocked[(src,dst)] = False
                        conn_blocked[(dst,src)] = False
                        logging.info("Unblocked digital connection %s<->%s (reported recovered)", src, dst)

# ---------------- Main loop ----------------
def main_loop():
    global _running
    logging.info("Starting proxy sync main loop")
    # initialize devices
    for name in cfg["devices"]["physical"].keys():
        device_fail_counts[name] = 0
        device_success_counts[name] = 0
        device_status[name] = True

    # initialize conn counters from expected_connections
    for s, targets in expected_connections.items():
        for t in targets:
            key = (s,t)
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

# ---------------- MQTT init + runner ----------------
def start_mqtt_listener():
    global mqtt_client
    broker_ip = cfg.get("mqtt", {}).get("host") or cfg["devices"]["physical"]["broker"]["ip"]
    broker_port = int(cfg.get("mqtt", {}).get("port", 1883))

    # Create client explicitly with MQTTv311 and callback API v2 to match other agents
    mqtt_client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    try:
        user = cfg.get("mqtt", {}).get("user")
        pwd = cfg.get("mqtt", {}).get("password")
        if user and pwd:
            mqtt_client.username_pw_set(user, pwd)
    except Exception:
        pass
    try:
        mqtt_client.connect(broker_ip, broker_port, MQTT_KEEPALIVE)
    except Exception as e:
        logging.exception("MQTT connect failed: %s", e)
    mqtt_client.loop_start()

# ---------------- shutdown ----------------
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

# ---------------- entrypoint ----------------
if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    load_config(CONFIG_FILE)
    start_mqtt_listener()
    main_loop()
