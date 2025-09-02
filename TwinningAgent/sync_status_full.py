#!/usr/bin/env python3
"""
sync_status_full.py
-------------------
Proxy agent to synchronize device UP/DOWN and per-connection health between
physical and digital twins.

- Pings physical devices (authoritative liveness)
- Listens to device-side MQTT health reports: <mqtt_prefix>/<src>/<dst>
  payload: {"status":"UP|DOWN","time":"<iso8601>"}
- Stops/starts digital nodes (GNS3 API) when physical changes
- Blocks/unblocks digital connections with iptables based on reports
- No flip-flop: holds blocks until explicit UP or min-block timer expires

Requires:
  pip install pyyaml requests paho-mqtt
"""

import json
import logging
import signal
import subprocess
import sys
import threading
import time
from typing import Dict, Tuple

import paho.mqtt.client as mqtt
import requests
import yaml
from requests.auth import HTTPBasicAuth

# ---------------- CONFIG ----------------
CONFIG_FILE = "devices.yaml"

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename="sync_status_full.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------- GLOBAL RUNTIME (filled after load) ----------------
cfg = {}
# monitor params
PING_COUNT = 1
PING_TIMEOUT = 2
CHECK_INTERVAL = 10
DEVICE_FAIL_THRESHOLD = 3
DEVICE_RECOVER_THRESHOLD = 3
CONN_FAIL_THRESHOLD = 1
CONN_RECOVER_THRESHOLD = 1
CONN_MIN_BLOCK_SECONDS = 30
IPTABLES_CHAIN = "FORWARD"
MQTT_PREFIX = "health"
MQTT_CLIENT_ID = "proxy-sync-agent"
MQTT_KEEPALIVE = 60

# device tracking
device_fail_counts: Dict[str, int] = {}
device_success_counts: Dict[str, int] = {}
device_status: Dict[str, bool] = {}  # True=UP, False=DOWN

# connection tracking
Key = Tuple[str, str]  # (src_name, dst_name)
conn_fail_counts: Dict[Key, int] = {}
conn_success_counts: Dict[Key, int] = {}
conn_reported_status: Dict[Key, bool] = {}  # True=UP, False=DOWN (debounced)
conn_blocked: Dict[Key, bool] = {}          # True if iptables block active (src->dst)
conn_blocked_since: Dict[Key, float] = {}    # timestamp of when block applied

# gns3 cache (optional perf)
gns3_node_running: Dict[str, bool] = {}

# control
_running = True
mqtt_client = None


# ---------------- UTIL ----------------
def load_config(path=CONFIG_FILE):
    global cfg, PING_COUNT, PING_TIMEOUT, CHECK_INTERVAL
    global DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD
    global CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD, CONN_MIN_BLOCK_SECONDS
    global IPTABLES_CHAIN, MQTT_PREFIX, MQTT_CLIENT_ID, MQTT_KEEPALIVE

    with open(path) as f:
        cfg = yaml.safe_load(f)

    mon = cfg.get("monitor", {}) or {}
    PING_COUNT = int(mon.get("ping_count", 1))
    PING_TIMEOUT = int(mon.get("ping_timeout", 2))
    CHECK_INTERVAL = int(mon.get("check_interval_seconds", 10))
    DEVICE_FAIL_THRESHOLD = int(mon.get("device_fail_threshold", 3))
    DEVICE_RECOVER_THRESHOLD = int(mon.get("device_recover_threshold", 3))
    CONN_FAIL_THRESHOLD = int(mon.get("connection_fail_threshold", 1))
    CONN_RECOVER_THRESHOLD = int(mon.get("connection_recover_threshold", 1))
    CONN_MIN_BLOCK_SECONDS = int(mon.get("connection_min_block_seconds", 30))
    IPTABLES_CHAIN = mon.get("iptables_chain", "FORWARD")
    MQTT_PREFIX = mon.get("mqtt_prefix", "health")

    mqc = cfg.get("mqtt", {}) or {}
    MQTT_CLIENT_ID = mqc.get("client_id", "proxy-sync-agent")
    MQTT_KEEPALIVE = int(mqc.get("keepalive", 60))

    logging.info(
        "Loaded config. INTERVAL=%s DEV_THR(fail=%s,recover=%s) "
        "CONN_THR(fail=%s,recover=%s) MIN_BLOCK=%ss CHAIN=%s PREFIX=%s",
        CHECK_INTERVAL, DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD,
        CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD,
        CONN_MIN_BLOCK_SECONDS, IPTABLES_CHAIN, MQTT_PREFIX
    )


def ping(ip: str, bind_ip: str = None) -> bool:
    try:
        cmd = ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT)]
        if bind_ip:
            cmd.extend(["-I", bind_ip])
        cmd.append(str(ip))
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception as e:
        logging.exception("Ping error: %s", e)
        return False


# ---------------- GNS3 ----------------
def gns3_request(method: str, endpoint: str, data=None):
    g = cfg["gns3"]
    base = g["url"].rstrip("/")
    url = f"{base}{endpoint}"
    try:
        r = requests.request(
            method, url, auth=HTTPBasicAuth(g["user"], g["password"]),
            timeout=8, json=data
        )
        if not r.ok:
            logging.warning("GNS3 %s %s -> %s %s", method, endpoint, r.status_code, r.text)
        return r
    except Exception as e:
        logging.exception("GNS3 request error: %s", e)
        return None


def start_node(node_id: str):
    project = cfg["gns3"]["project_id"]
    r = gns3_request("POST", f"/projects/{project}/nodes/{node_id}/start")
    if r is not None and r.ok:
        gns3_node_running[node_id] = True
        logging.info("Started node %s", node_id)
        return True
    return False


def stop_node(node_id: str):
    project = cfg["gns3"]["project_id"]
    r = gns3_request("POST", f"/projects/{project}/nodes/{node_id}/stop")
    if r is not None and r.ok:
        gns3_node_running[node_id] = False
        logging.info("Stopped node %s", node_id)
        return True
    return False


# ---------------- iptables helpers ----------------
def _rule_exists(src_ip: str, dst_ip: str) -> bool:
    try:
        res = subprocess.run(
            ["iptables", "-C", IPTABLES_CHAIN, "-s", src_ip, "-d", dst_ip, "-j", "DROP"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return res.returncode == 0
    except Exception:
        return False


def add_block_pair(a: str, b: str):
    # a->b
    if not _rule_exists(a, b):
        subprocess.run(["iptables", "-A", IPTABLES_CHAIN, "-s", a, "-d", b, "-j", "DROP"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info("Block added %s -> %s", a, b)
    # b->a
    if not _rule_exists(b, a):
        subprocess.run(["iptables", "-A", IPTABLES_CHAIN, "-s", b, "-d", a, "-j", "DROP"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info("Block added %s -> %s", b, a)


def remove_block_pair(a: str, b: str):
    # remove all occurrences if duplicates exist
    while _rule_exists(a, b):
        subprocess.run(["iptables", "-D", IPTABLES_CHAIN, "-s", a, "-d", b, "-j", "DROP"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info("Block removed %s -> %s", a, b)
    while _rule_exists(b, a):
        subprocess.run(["iptables", "-D", IPTABLES_CHAIN, "-s", b, "-d", a, "-j", "DROP"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info("Block removed %s -> %s", b, a)


def _apply_block(src: str, dst: str, sip: str, dip: str):
    key = (src, dst)
    if not conn_blocked.get(key, False):
        add_block_pair(sip, dip)
        conn_blocked[key] = True
        conn_blocked_since[key] = time.time()
        # mirror key to keep bookkeeping symmetric
        mkey = (dst, src)
        conn_blocked[mkey] = True
        conn_blocked_since[mkey] = conn_blocked_since[key]
        logging.info("Digital connection BLOCKED %s <-> %s", src, dst)


def _lift_block(src: str, dst: str, sip: str, dip: str):
    key = (src, dst)
    if conn_blocked.get(key, False):
        remove_block_pair(sip, dip)
        for k in [(src, dst), (dst, src)]:
            conn_blocked[k] = False
            conn_blocked_since.pop(k, None)
        logging.info("Digital connection UNBLOCKED %s <-> %s", src, dst)


# ---------------- MQTT ----------------
def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    topic = f"{MQTT_PREFIX}/#"
    client.subscribe(topic)
    logging.info("MQTT connected rc=%s; subscribed to %s", reason_code, topic)


def on_mqtt_message(client, userdata, msg):
    try:
        # topic: <prefix>/<src>/<dst>
        parts = msg.topic.split("/")
        if len(parts) < 3:
            return
        _, src, dst = parts[:3]
        payload = msg.payload.decode(errors="ignore").strip()
        status = None
        try:
            js = json.loads(payload)
            status = str(js.get("status", "")).upper()
        except Exception:
            status = payload.upper()

        if status not in ("UP", "DOWN"):
            return

        key = (src, dst)
        if status == "DOWN":
            conn_fail_counts[key] = conn_fail_counts.get(key, 0) + 1
            conn_success_counts[key] = 0
            # transition to DOWN only when threshold met
            if conn_fail_counts[key] >= CONN_FAIL_THRESHOLD and conn_reported_status.get(key, True):
                conn_reported_status[key] = False
                logging.info("Report debounced: %s->%s DOWN", src, dst)
        else:  # "UP"
            conn_success_counts[key] = conn_success_counts.get(key, 0) + 1
            conn_fail_counts[key] = 0
            if conn_success_counts[key] >= CONN_RECOVER_THRESHOLD and not conn_reported_status.get(key, True):
                conn_reported_status[key] = True
                logging.info("Report debounced: %s->%s UP", src, dst)

    except Exception as e:
        logging.exception("MQTT message error on %s: %s", msg.topic, e)


def start_mqtt_listener():
    global mqtt_client
    mqc = cfg.get("mqtt", {}) or {}
    host = mqc.get("host") or cfg["devices"]["physical"]["broker"]["ip"]
    port = int(mqc.get("port", 1883))
    user = mqc.get("user")
    pwd = mqc.get("password")

    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
    if user and pwd:
        mqtt_client.username_pw_set(user, pwd)
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    try:
        mqtt_client.connect(host, port, MQTT_KEEPALIVE)
        threading.Thread(target=mqtt_client.loop_forever, daemon=True).start()
    except Exception as e:
        logging.exception("MQTT connect failed: %s", e)


# ---------------- CORE LOGIC ----------------
def process_device_checks():
    phys = cfg["devices"]["physical"]
    digi = cfg["devices"]["digital"]

    for name, info in phys.items():
        ip = str(info["ip"])
        bind_ip = info.get("bind_ip")
        alive = ping(ip, bind_ip)

        # debounce
        if alive:
            device_success_counts[name] = device_success_counts.get(name, 0) + 1
            device_fail_counts[name] = 0
        else:
            device_fail_counts[name] = device_fail_counts.get(name, 0) + 1
            device_success_counts[name] = 0

        prev = device_status.get(name, True)

        # transition to DOWN
        if not alive and prev and device_fail_counts[name] >= DEVICE_FAIL_THRESHOLD:
            device_status[name] = False
            logging.warning("Device %s declared DOWN", name)
            # stop twin
            node_id = cfg["devices"]["digital"].get(name, {}).get("gns3_node_id")
            if node_id:
                stop_node(node_id)
            # block all connections touching this node
            di_ip = digi.get(name, {}).get("ip")
            if di_ip:
                for other, oinfo in digi.items():
                    if other == name:
                        continue
                    oi = oinfo.get("ip")
                    if oi:
                        _apply_block(name, other, di_ip, oi)

        # transition to UP
        if alive and not prev and device_success_counts[name] >= DEVICE_RECOVER_THRESHOLD:
            device_status[name] = True
            logging.info("Device %s recovered", name)
            # start twin
            node_id = cfg["devices"]["digital"].get(name, {}).get("gns3_node_id")
            if node_id:
                start_node(node_id)
            # unblock pairs involving this node (if they’re not still reported DOWN)
            di_ip = digi.get(name, {}).get("ip")
            if di_ip:
                for other, oinfo in digi.items():
                    if other == name:
                        continue
                    oi = oinfo.get("ip")
                    if oi:
                        # only lift if there isn't an explicit DOWN report that still stands
                        k1, k2 = (name, other), (other, name)
                        explicit_down = (conn_reported_status.get(k1, True) is False or
                                         conn_reported_status.get(k2, True) is False)
                        if not explicit_down:
                            _lift_block(name, other, di_ip, oi)


def process_connection_reports():
    """Apply/remedy blocks purely from debounced device reports.
       Do NOT assume UP when nothing arrives."""
    phys = cfg["devices"]["physical"]
    digi = cfg["devices"]["digital"]

    # figure list of expected relationships from YAML "connections"
    expected = []
    for src, sinfo in phys.items():
        for dst in (sinfo.get("connections") or []):
            expected.append((src, dst))

    for (src, dst) in expected:
        # skip if either physical device is DOWN (device logic already handled blocks)
        if not device_status.get(src, True) or not device_status.get(dst, True):
            continue

        reported_up = conn_reported_status.get((src, dst), True)
        sip = digi.get(src, {}).get("ip")
        dip = digi.get(dst, {}).get("ip")
        if not (sip and dip):
            continue

        if not reported_up:
            _apply_block(src, dst, sip, dip)
        else:
            # Unblock only if it was previously blocked AND we have explicit UP
            if conn_blocked.get((src, dst), False):
                _lift_block(src, dst, sip, dip)


def sweep_expired_blocks():
    """Safety valve: if a block has been in place longer than CONN_MIN_BLOCK_SECONDS
    without any explicit continuing DOWN, lift it."""
    now = time.time()
    digi = cfg["devices"]["digital"]

    # build reverse lookup for IPs
    name_to_ip = {n: i.get("ip") for n, i in digi.items()}

    for key, since in list(conn_blocked_since.items()):
        age = now - since
        if age < CONN_MIN_BLOCK_SECONDS:
            continue

        src, dst = key
        # if either device is DOWN physically, keep block
        if not device_status.get(src, True) or not device_status.get(dst, True):
            continue

        # if still explicitly reported DOWN, keep block
        still_down = (conn_reported_status.get((src, dst), True) is False or
                      conn_reported_status.get((dst, src), True) is False)
        if still_down:
            continue

        sip, dip = name_to_ip.get(src), name_to_ip.get(dst)
        if sip and dip:
            logging.info("Min-block timer expired for %s<->%s (%.1fs) — lifting", src, dst, age)
            _lift_block(src, dst, sip, dip)


# ---------------- MAIN LOOP ----------------
def main_loop():
    phys = cfg["devices"]["physical"]

    # init device state
    for name in phys.keys():
        device_fail_counts[name] = 0
        device_success_counts[name] = 0
        device_status[name] = True  # optimistic start

    # init connection state from YAML connections
    for src, sinfo in phys.items():
        for dst in (sinfo.get("connections") or []):
            k = (src, dst)
            conn_fail_counts[k] = 0
            conn_success_counts[k] = 0
            conn_reported_status[k] = True
            conn_blocked[k] = False

    logging.info("Proxy sync main loop started")
    while _running:
        try:
            process_device_checks()
            process_connection_reports()
            sweep_expired_blocks()
        except Exception as e:
            logging.exception("Main loop error: %s", e)
        time.sleep(CHECK_INTERVAL)


# ---------------- SHUTDOWN ----------------
def shutdown(*_):
    global _running
    logging.info("Shutdown requested")
    _running = False
    try:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
    except Exception:
        pass
    sys.exit(0)


# ---------------- ENTRY ----------------
if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    load_config(CONFIG_FILE)
    start_mqtt_listener()
    main_loop()
