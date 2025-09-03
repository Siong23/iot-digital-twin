#!/usr/bin/env python3
"""
sync_status_full.py (ACL-backend)

Proxy master:
- Pings physical devices → stop/start digital nodes via GNS3 API
- Subscribes to device-side health reports (MQTT topic: health/<src>/<dst>)
- Instructs the digital router (SSH) to add/remove ACL deny lines in a named ACL
  instead of manipulating the proxy iptables.
- Proxy is authoritative: if proxy can't reach a device, it is considered DOWN.

Requires: paramiko, paho-mqtt, requests, pyyaml
Install: sudo pip3 install paramiko paho-mqtt requests pyyaml
"""
import os
import time
import json
import yaml
import logging
import subprocess
import threading
import signal
import sys
import re
from typing import Dict, Tuple, List

import requests
from requests.auth import HTTPBasicAuth
import paho.mqtt.client as mqtt
import paramiko
import socket

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
    "IPTABLES_CHAIN": "FORWARD",  # kept for compatibility though unused
    "MQTT_CLIENT_ID": "proxy-sync-agent",
    "MQTT_KEEPALIVE": 60,
    "ROUTER_ACL_NAME": "BLOCKED",
    "ROUTER_WRITE_MEMORY": False,
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
MQTT_CLIENT_ID = DEFAULTS["MQTT_CLIENT_ID"]
MQTT_KEEPALIVE = DEFAULTS["MQTT_KEEPALIVE"]

# Router SSH settings (populated from YAML)
ROUTER_SSH_USER = None
ROUTER_SSH_PASS = None
ROUTER_ENABLE_PASS = None
ROUTER_ACL_NAME = DEFAULTS["ROUTER_ACL_NAME"]
ROUTER_WRITE_MEMORY = DEFAULTS["ROUTER_WRITE_MEMORY"]

# device_name -> dict { ip, bind_ip, ... }
device_fail_counts: Dict[str,int] = {}
device_success_counts: Dict[str,int] = {}
device_status: Dict[str,bool] = {}   # True=UP, False=DOWN

# connection reported state and counters
conn_fail_counts: Dict[Tuple[str,str],int] = {}
conn_success_counts: Dict[Tuple[str,str],int] = {}
conn_reported_status: Dict[Tuple[str,str],bool] = {}  # latest reported by devices (True=UP)

# digital-side block state (to avoid duplicate ops)
conn_blocked: Dict[Tuple[str,str],bool] = {}

# GNS3 node running cache
gns3_node_running: Dict[str,bool] = {}

# MQTT client (initialized later)
mqtt_client = None

# Graceful shutdown flag
_running = True

# ---------------- HELPERS ----------------
def load_config(path=CONFIG_FILE):
    """Load YAML and apply monitor/mqtt/router overrides to runtime variables."""
    global cfg, PING_COUNT, PING_TIMEOUT, CHECK_INTERVAL
    global DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD
    global CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD
    global MQTT_CLIENT_ID, MQTT_KEEPALIVE
    global ROUTER_SSH_USER, ROUTER_SSH_PASS, ROUTER_ENABLE_PASS, ROUTER_ACL_NAME, ROUTER_WRITE_MEMORY

    with open(path) as f:
        cfg = yaml.safe_load(f)

    logging.info("Loaded config from %s", path)

    monitor_cfg = cfg.get("monitor", {})
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

    PING_COUNT = int(monitor_cfg.get("ping_count", DEFAULTS["PING_COUNT"]))
    PING_TIMEOUT = int(monitor_cfg.get("ping_timeout", DEFAULTS["PING_TIMEOUT"]))

    mqtt_cfg = cfg.get("mqtt", {})
    MQTT_CLIENT_ID = mqtt_cfg.get("client_id", DEFAULTS["MQTT_CLIENT_ID"])
    MQTT_KEEPALIVE = int(mqtt_cfg.get("keepalive", DEFAULTS["MQTT_KEEPALIVE"]))

    # Router SSH / ACL config (top-level 'router' block in YAML)
    router_cfg = cfg.get("router", {})
    ROUTER_SSH_USER = router_cfg.get("user")
    ROUTER_SSH_PASS = router_cfg.get("password")
    ROUTER_ENABLE_PASS = router_cfg.get("enable_password")
    ROUTER_ACL_NAME = router_cfg.get("acl_name", DEFAULTS["ROUTER_ACL_NAME"])
    ROUTER_WRITE_MEMORY = bool(router_cfg.get("write_memory", DEFAULTS["ROUTER_WRITE_MEMORY"]))

    logging.info(
        "Runtime params: CHECK_INTERVAL=%s, DEVICE_FAIL_THRESHOLD=%s, DEVICE_RECOVER_THRESHOLD=%s, CONN_FAIL_THRESHOLD=%s, CONN_RECOVER_THRESHOLD=%s, ROUTER_ACL=%s",
        CHECK_INTERVAL, DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD, CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD, ROUTER_ACL_NAME
    )

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

# ---------------- Router SSH helpers (ACL management) ----------------
def _router_ssh_run(commands: List[str], timeout: int = 8) -> str:
    """
    Open SSH to the DIGITAL router and run commands via an interactive shell.
    Returns combined output.
    """
    dig_router = cfg["devices"]["digital"]["router"]
    host = dig_router.get("ip")
    user = ROUTER_SSH_USER
    pwd = ROUTER_SSH_PASS
    enable_pwd = ROUTER_ENABLE_PASS

    if not host or not user or not pwd:
        raise RuntimeError("Router SSH credentials/host not configured in devices.yaml -> router block")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, username=user, password=pwd, look_for_keys=False, allow_agent=False, timeout=10)
        chan = client.invoke_shell()
        time.sleep(0.3)
        # clear initial banner
        _drain_channel(chan)
        # if privileged mode required, try 'enable'
        if enable_pwd:
            chan.send("enable\n")
            time.sleep(0.2)
            _drain_channel(chan)
            chan.send(enable_pwd + "\n")
            time.sleep(0.3)
            _drain_channel(chan)

        # Enter config mode
        chan.send("configure terminal\n")
        time.sleep(0.2)
        _drain_channel(chan)
        out_combined = ""
        for c in commands:
            chan.send(c + "\n")
            time.sleep(0.25)
            out = _drain_channel(chan)
            out_combined += out
        # exit config
        chan.send("end\n")
        time.sleep(0.2)
        out_combined += _drain_channel(chan)
        # optionally write memory
        if ROUTER_WRITE_MEMORY:
            chan.send("write memory\n")
            time.sleep(0.8)
            out_combined += _drain_channel(chan)
        chan.close()
        client.close()
        return out_combined
    except Exception as e:
        logging.exception("Router SSH error: %s", e)
        try:
            client.close()
        except:
            pass
        raise

def _drain_channel(chan, timeout=1.0) -> str:
    """
    Read available data from channel; wait up to `timeout` seconds for data.
    """
    out = ""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if chan.recv_ready():
            try:
                data = chan.recv(65536)
                out += data.decode(errors="ignore")
            except Exception:
                break
        else:
            time.sleep(0.05)
    return out

def _show_acl() -> str:
    """Return 'show ip access-lists <ACL>' output by using exec_command (non-config)."""
    dig_router = cfg["devices"]["digital"]["router"]
    host = dig_router.get("ip")
    user = ROUTER_SSH_USER
    pwd = ROUTER_SSH_PASS
    if not host or not user or not pwd:
        raise RuntimeError("Router SSH credentials/host not configured in devices.yaml -> router block")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, username=user, password=pwd, look_for_keys=False, allow_agent=False, timeout=8)
        cmd = f"show ip access-lists {ROUTER_ACL_NAME}\n"
        stdin, stdout, stderr = client.exec_command(cmd, timeout=8)
        out = stdout.read().decode(errors="ignore")
        client.close()
        return out
    except Exception as e:
        logging.exception("Router show ACL error: %s", e)
        try: client.close()
        except: pass
        return ""

def _acl_has_line(src_ip: str, dst_ip: str) -> bool:
    out = _show_acl()
    if not out:
        return False
    # robust regex: allow variable whitespace, optional sequence numbers
    pattern = rf"deny\s+ip\s+host\s+{re.escape(src_ip)}\s+host\s+{re.escape(dst_ip)}"
    return bool(re.search(pattern, out, flags=re.IGNORECASE))

def add_block(src_ip: str, dst_ip: str):
    """
    Ensure ACL contains deny A->B and deny B->A (bidirectional block).
    Update conn_blocked for both directions.
    """
    try:
        need_cmds = []
        # add forward if missing
        if not _acl_has_line(src_ip, dst_ip):
            need_cmds.append(f"ip access-list extended {ROUTER_ACL_NAME}")
            need_cmds.append(f"deny ip host {src_ip} host {dst_ip}")
        # add reverse if missing
        if not _acl_has_line(dst_ip, src_ip):
            # ensure ACL context only once
            if not need_cmds:
                need_cmds.append(f"ip access-list extended {ROUTER_ACL_NAME}")
            need_cmds.append(f"deny ip host {dst_ip} host {src_ip}")

        if need_cmds:
            _router_ssh_run(need_cmds)
            logging.info("Added router ACL block %s <-> %s", src_ip, dst_ip)
        else:
            logging.info("Router ACL already contains bidir block %s <-> %s", src_ip, dst_ip)

        # record both directions as blocked in memory
        # (use device names mapping outside; here we mark by IP tuple)
        conn_blocked[(src_ip, dst_ip)] = True
        conn_blocked[(dst_ip, src_ip)] = True

    except Exception as e:
        logging.exception("Failed to add router ACL block %s <-> %s: %s", src_ip, dst_ip, e)


def remove_block(src_ip: str, dst_ip: str):
    """
    Remove deny A->B and deny B->A from the ACL (if present).
    Clear conn_blocked for both directions in memory.
    """
    try:
        cmds = []
        if _acl_has_line(src_ip, dst_ip):
            cmds.append(f"ip access-list extended {ROUTER_ACL_NAME}")
            cmds.append(f"no deny ip host {src_ip} host {dst_ip}")
        if _acl_has_line(dst_ip, src_ip):
            if not cmds:
                cmds.append(f"ip access-list extended {ROUTER_ACL_NAME}")
            cmds.append(f"no deny ip host {dst_ip} host {src_ip}")

        if cmds:
            _router_ssh_run(cmds)
            logging.info("Removed router ACL block %s <-> %s", src_ip, dst_ip)
        else:
            logging.info("Router ACL had no block entries for %s <-> %s", src_ip, dst_ip)

        # clear memory state both directions
        conn_blocked[(src_ip, dst_ip)] = False
        conn_blocked[(dst_ip, src_ip)] = False

    except Exception as e:
        logging.exception("Failed to remove router ACL block %s <-> %s: %s", src_ip, dst_ip, e)


# ---------------- MQTT handling for device reports ----------------
def on_mqtt_connect(client, userdata, flags, rc):
    logging.info("Connected to MQTT broker (rc=%s) -- subscribing to health/#", rc)
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
                            # instruct router to block flows between digi_ip and other_ip
                            add_block(digi_ip, other_ip)
                            conn_blocked[(name, other_name)] = True
                            conn_blocked[(other_name, name)] = True

        if device_success_counts.get(name,0) >= DEVICE_RECOVER_THRESHOLD:
            if prev is None or prev is False:
                device_status[name] = True
                logging.info("Device %s recovered (after %d successes)", name, device_success_counts[name])
                if name in digi and digi[name].get("gns3_node_id"):
                    start_node(digi[name].get("gns3_node_id"))
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

    expected = {
        "broker": ["sensor", "ipcam"],
        "router": ["broker", "ipcam", "sensor"],
        "sensor": ["broker", "router"],
        "ipcam": []
    }

    for src, targets in expected.items():
        for dst in targets:
            key = (src, dst)
            reported_up = conn_reported_status.get(key, True)
            src_up = device_status.get(src, True)
            dst_up = device_status.get(dst, True)
            if not src_up or not dst_up:
                # authoritative: block digital side when either device is down
                if src in digi and dst in digi:
                    sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                    if not conn_blocked.get((src,dst), False):
                        add_block(sip, dip)
                        conn_blocked[(src,dst)] = True
                        conn_blocked[(dst,src)] = True
                        logging.info("Blocking digital connection %s->%s due to device DOWN (proxy authoritative)", src, dst)
                continue

            # respect device-reported connection state
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
    for name in cfg["devices"]["physical"].keys():
        device_fail_counts[name] = 0
        device_success_counts[name] = 0
        device_status[name] = True

    expected = {
        "broker": ["sensor", "ipcam"],
        "router": ["broker", "ipcam", "sensor"],
        "sensor": ["broker", "router"],
        "ipcam": []
    }
    for s, targets in expected.items():
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
    mqtt_client = mqtt.Client(MQTT_CLIENT_ID)
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
