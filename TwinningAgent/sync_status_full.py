#!/usr/bin/env python3
"""
sync_status_full.py

Proxy master:
- Pings physical devices → stop/start digital nodes via GNS3 API
- Subscribes to device-side health reports (MQTT topic: health/<src>/<dst>)
- Enforces digital-side blocking by SSHing to the digital VMs (broker/sensor) and
  running `sudo iptables -A/D OUTPUT -d <peer_ip> -j REJECT`, and for the digital router
  inserting/removing `ip route <VM_IP> 255.255.255.255 Null0`.
- Proxy is authoritative: if proxy can't reach a device, it is considered DOWN.

Requirements:
    pip3 install paramiko paho-mqtt requests pyyaml
"""

import os
import time
import json
import yaml
import logging
import subprocess
import signal
import sys
import re
import socket
from typing import Dict, Tuple, List, Optional

import requests
from requests.auth import HTTPBasicAuth
import paho.mqtt.client as mqtt
import paramiko

# ---------------- CONFIG FILE ----------------
CONFIG_FILE = "devices.yaml"

# ---------------- DEFAULTS ----------------
DEFAULTS = {
    "PING_COUNT": 1,
    "PING_TIMEOUT": 2,
    "CHECK_INTERVAL": 10,
    "DEVICE_FAIL_THRESHOLD": 3,
    "DEVICE_RECOVER_THRESHOLD": 3,
    "CONN_FAIL_THRESHOLD": 1,
    "CONN_RECOVER_THRESHOLD": 1,
    "MQTT_CLIENT_ID": "proxy-sync-agent",
    "MQTT_KEEPALIVE": 60,
    "ROUTER_ACL_NAME": "BLOCKED",
    "ROUTER_WRITE_MEMORY": False,
}

# ---------------- LOGGING ----------------
LOGFILE = "sync_status_full.log"
logging.basicConfig(
    filename=LOGFILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger("").addHandler(console)

# ---------------- GLOBAL STATE ----------------
cfg: dict = {}
# runtime params (populated on load)
PING_COUNT = DEFAULTS["PING_COUNT"]
PING_TIMEOUT = DEFAULTS["PING_TIMEOUT"]
CHECK_INTERVAL = DEFAULTS["CHECK_INTERVAL"]
DEVICE_FAIL_THRESHOLD = DEFAULTS["DEVICE_FAIL_THRESHOLD"]
DEVICE_RECOVER_THRESHOLD = DEFAULTS["DEVICE_RECOVER_THRESHOLD"]
CONN_FAIL_THRESHOLD = DEFAULTS["CONN_FAIL_THRESHOLD"]
CONN_RECOVER_THRESHOLD = DEFAULTS["CONN_RECOVER_THRESHOLD"]
MQTT_CLIENT_ID = DEFAULTS["MQTT_CLIENT_ID"]
MQTT_KEEPALIVE = DEFAULTS["MQTT_KEEPALIVE"]

# Router SSH (top-level router block)
ROUTER_SSH_USER: Optional[str] = None
ROUTER_SSH_PASS: Optional[str] = None
ROUTER_ENABLE_PASS: Optional[str] = None
ROUTER_ACL_NAME: str = DEFAULTS["ROUTER_ACL_NAME"]
ROUTER_WRITE_MEMORY: bool = DEFAULTS["ROUTER_WRITE_MEMORY"]

# monitor state
device_fail_counts: Dict[str, int] = {}
device_success_counts: Dict[str, int] = {}
device_status: Dict[str, bool] = {}     # True=UP, False=DOWN

conn_fail_counts: Dict[Tuple[str, str], int] = {}
conn_success_counts: Dict[Tuple[str, str], int] = {}
conn_reported_status: Dict[Tuple[str, str], bool] = {}

# whether we applied an enforced block in digi view
conn_blocked: Dict[Tuple[str, str], bool] = {}

# GNS3 node running cache
gns3_node_running: Dict[str, bool] = {}

# MQTT client
mqtt_client: Optional[mqtt.Client] = None

# runtime flag
_running = True

# ---------------- UTILITIES ----------------
def now_iso():
    from datetime import datetime
    return datetime.utcnow().isoformat()

def load_config(path: str = CONFIG_FILE):
    global cfg, PING_COUNT, PING_TIMEOUT, CHECK_INTERVAL
    global DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD
    global CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD
    global MQTT_CLIENT_ID, MQTT_KEEPALIVE
    global ROUTER_SSH_USER, ROUTER_SSH_PASS, ROUTER_ENABLE_PASS, ROUTER_ACL_NAME, ROUTER_WRITE_MEMORY

    with open(path) as f:
        cfg = yaml.safe_load(f)

    logging.info("Loaded config from %s", path)

    monitor = cfg.get("monitor", {})
    def _get_int(k, default):
        v = monitor.get(k)
        try:
            return int(v) if v is not None else default
        except Exception:
            return default

    CHECK_INTERVAL = _get_int("check_interval_seconds", DEFAULTS["CHECK_INTERVAL"])
    DEVICE_FAIL_THRESHOLD = _get_int("device_fail_threshold", DEFAULTS["DEVICE_FAIL_THRESHOLD"])
    DEVICE_RECOVER_THRESHOLD = _get_int("device_recover_threshold", DEFAULTS["DEVICE_RECOVER_THRESHOLD"])
    CONN_FAIL_THRESHOLD = _get_int("connection_fail_threshold", DEFAULTS["CONN_FAIL_THRESHOLD"])
    CONN_RECOVER_THRESHOLD = _get_int("connection_recover_threshold", DEFAULTS["CONN_RECOVER_THRESHOLD"])
    PING_COUNT = int(monitor.get("ping_count", DEFAULTS["PING_COUNT"]))
    PING_TIMEOUT = int(monitor.get("ping_timeout", DEFAULTS["PING_TIMEOUT"]))

    mqtt_cfg = cfg.get("mqtt", {})
    MQTT_CLIENT_ID = mqtt_cfg.get("client_id", DEFAULTS["MQTT_CLIENT_ID"])
    MQTT_KEEPALIVE = int(mqtt_cfg.get("keepalive", DEFAULTS["MQTT_KEEPALIVE"]))

    router_cfg = cfg.get("router", {}) or {}
    ROUTER_SSH_USER = router_cfg.get("user")
    ROUTER_SSH_PASS = router_cfg.get("password")
    ROUTER_ENABLE_PASS = router_cfg.get("enable_password")
    ROUTER_ACL_NAME = router_cfg.get("acl_name", DEFAULTS["ROUTER_ACL_NAME"])
    ROUTER_WRITE_MEMORY = bool(router_cfg.get("write_memory", DEFAULTS["ROUTER_WRITE_MEMORY"]))

    logging.info("Runtime: interval=%s, device_fail=%s recover=%s, conn_fail=%s recover=%s, router_acl=%s",
                 CHECK_INTERVAL, DEVICE_FAIL_THRESHOLD, DEVICE_RECOVER_THRESHOLD, CONN_FAIL_THRESHOLD, CONN_RECOVER_THRESHOLD, ROUTER_ACL_NAME)

def ping(ip: str, bind_ip: Optional[str] = None) -> bool:
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

# ---------------- GNS3 helpers ----------------
def gns3_request(method: str, endpoint: str, data=None, json_body: bool = True):
    try:
        g = cfg["gns3"]
        base = g["url"].rstrip("/")
        url = f"{base}{endpoint}"
        r = requests.request(method, url, auth=HTTPBasicAuth(g["user"], g["password"]), timeout=8, json=data if json_body else None)
        if not r.ok:
            logging.warning("GNS3 %s %s -> %s: %s", method, url, r.status_code, r.text)
        return r
    except Exception as e:
        logging.exception("GNS3 request error: %s", e)
        return None

def start_node(node_id: str) -> bool:
    project = cfg["gns3"]["project_id"]
    logging.info("Starting GNS3 node %s", node_id)
    r = gns3_request("POST", f"/projects/{project}/nodes/{node_id}/start")
    if r and r.ok:
        gns3_node_running[node_id] = True
        return True
    return False

def stop_node(node_id: str) -> bool:
    project = cfg["gns3"]["project_id"]
    logging.info("Stopping GNS3 node %s", node_id)
    r = gns3_request("POST", f"/projects/{project}/nodes/{node_id}/stop")
    if r and r.ok:
        gns3_node_running[node_id] = False
        return True
    return False

# ---------------- SSH helpers for digital VMs and router ----------------
def _open_bound_transport(host: str, username: str, password: str, bind_ip: Optional[str] = None, timeout: int = 10) -> paramiko.Transport:
    """
    Open a Paramiko Transport on a socket bound to bind_ip (if provided).
    Caller must close transport.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if bind_ip:
        try:
            sock.bind((bind_ip, 0))
        except Exception as e:
            logging.exception("Failed to bind %s: %s", bind_ip, e)
            sock.close()
            raise
    sock.settimeout(timeout)
    sock.connect((host, 22))
    transport = paramiko.Transport(sock)
    transport.start_client(timeout=timeout)
    transport.auth_password(username, password)
    return transport

def _exec_command_on_host(host: str, username: str, password: str, cmd: str, bind_ip: Optional[str] = None, timeout: int = 15) -> Tuple[int, str, str]:
    """
    Execute single command on remote host using bound transport.
    Returns (exit_status, stdout, stderr).
    """
    transport = None
    chan = None
    try:
        transport = _open_bound_transport(host, username, password, bind_ip, timeout=10)
        chan = transport.open_session()
        chan.get_pty()
        chan.exec_command(cmd)
        out_chunks = []
        err_chunks = []
        start = time.time()
        while True:
            if chan.recv_ready():
                out_chunks.append(chan.recv(32768).decode(errors="ignore"))
            if chan.recv_stderr_ready():
                err_chunks.append(chan.recv_stderr(32768).decode(errors="ignore"))
            if chan.exit_status_ready():
                break
            if time.time() - start > timeout:
                logging.warning("SSH command timeout on %s: %s", host, cmd)
                break
            time.sleep(0.05)
        try:
            exit_status = chan.recv_exit_status()
        except Exception:
            exit_status = -1
        stdout = "".join(out_chunks)
        stderr = "".join(err_chunks)
        return exit_status, stdout, stderr
    finally:
        try:
            if chan:
                chan.close()
        except Exception:
            pass
        try:
            if transport:
                transport.close()
        except Exception:
            pass

def _run_sudo_cmd(host: str, user: str, password: str, cmd: str, bind_ip: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    Attempt to run `cmd` under sudo on the remote host.
    First try `sudo -n` (no password). If that fails, fallback to 'echo <pwd> | sudo -S -p "" <cmd>'.
    Returns (success_bool, stdout, stderr).
    """
    # try no-password sudo
    test_cmd = f"sudo -n {cmd}"
    rc, out, err = _exec_command_on_host(host, user, password, test_cmd, bind_ip=bind_ip, timeout=6)
    if rc == 0:
        return True, out, err
    # fallback
    safe_pwd = password.replace("'", "'\"'\"'")
    echo_cmd = f"echo '{safe_pwd}' | sudo -S -p '' {cmd}"
    rc2, out2, err2 = _exec_command_on_host(host, user, password, echo_cmd, bind_ip=bind_ip, timeout=10)
    return (rc2 == 0), out2, err2

def _router_ssh_run(commands: List[str], timeout: int = 10) -> str:
    """
    Run a sequence of config commands on the digital router via SSH (invoke_shell).
    Returns combined output.
    """
    dig_router = cfg["devices"]["digital"]["router"]
    host = dig_router.get("ip")
    user = ROUTER_SSH_USER
    pwd = ROUTER_SSH_PASS
    enable_pwd = ROUTER_ENABLE_PASS

    if not host or not user or not pwd:
        raise RuntimeError("Digital router SSH credentials not configured in YAML (top-level 'router' block).")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    out_combined = ""
    try:
        client.connect(hostname=host, username=user, password=pwd, look_for_keys=False, allow_agent=False, timeout=8)
        chan = client.invoke_shell()
        time.sleep(0.3)
        _drain_channel(chan)
        # if router needs 'enable' and is not at privileged prompt
        if enable_pwd:
            chan.send("enable\n")
            time.sleep(0.2)
            _drain_channel(chan)
            chan.send(enable_pwd + "\n")
            time.sleep(0.2)
            _drain_channel(chan)
        chan.send("configure terminal\n")
        time.sleep(0.15)
        _drain_channel(chan)
        for c in commands:
            chan.send(c + "\n")
            time.sleep(0.25)
            out_combined += _drain_channel(chan)
        chan.send("end\n")
        time.sleep(0.2)
        out_combined += _drain_channel(chan)
        if ROUTER_WRITE_MEMORY:
            chan.send("write memory\n")
            time.sleep(0.8)
            out_combined += _drain_channel(chan)
        try:
            chan.close()
        except Exception:
            pass
        client.close()
        return out_combined
    except Exception as e:
        logging.exception("Router SSH error: %s", e)
        try:
            client.close()
        except:
            pass
        raise

def _drain_channel(chan, timeout: float = 0.5) -> str:
    out = ""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if chan.recv_ready():
            try:
                out += chan.recv(65536).decode(errors="ignore")
            except Exception:
                break
        else:
            time.sleep(0.03)
    return out

# ---------------- Helpers to find digital devices ----------------
def _find_digital_device_by_ip(ip: str) -> Tuple[Optional[str], Optional[dict]]:
    for name, info in cfg["devices"]["digital"].items():
        if str(info.get("ip")) == str(ip):
            return name, info
    return None, None

# ---------------- Enforcement (block/unblock) ----------------
def add_block(src_ip: str, dst_ip: str):
    """
    Enforce a digital-side block between src_ip and dst_ip.
      - If either side is digital router -> use router Null0 route
      - Else SSH into VM(s) and add sudo iptables rule on OUTPUT to reject destination
      - Apply symmetric block if possible (both VM OUTPUTs)
    """
    src_name, src_info = _find_digital_device_by_ip(src_ip)
    dst_name, dst_info = _find_digital_device_by_ip(dst_ip)

    # ROUTER case
    if src_name == "router" or dst_name == "router":
        # target IP is the remote endpoint to null-route
        target_ip = dst_ip if src_name == "router" else src_ip
        logging.info("Adding Null0 route on digital router for %s", target_ip)
        try:
            _router_ssh_run([f"ip route {target_ip} 255.255.255.255 Null0"])
            conn_blocked[(src_name or src_ip, dst_name or dst_ip)] = True
        except Exception as e:
            logging.exception("Failed to add Null0 route for %s: %s", target_ip, e)
        return

    # VM case: add iptables OUTPUT -d dst_ip -j REJECT on src VM
    if src_info and src_info.get("ssh_user") and src_info.get("ssh_password"):
        host = src_info["ip"]
        user = src_info["ssh_user"]
        pwd = src_info["ssh_password"]
        bind_ip = src_info.get("bind_ip")
        # check if rule exists (no-password sudo check)
        check_cmd = f"iptables -C OUTPUT -d {dst_ip} -j REJECT"
        rc, out, err = _exec_command_on_host(host, user, pwd, f"sudo -n {check_cmd}", bind_ip=bind_ip, timeout=6)
        if rc == 0:
            logging.info("iptables rule already present on %s -> %s", host, dst_ip)
        else:
            ok, o, e = _run_sudo_cmd(host, user, pwd, check_cmd, bind_ip=bind_ip)
            if ok:
                logging.info("Added iptables REJECT on %s -> %s", host, dst_ip)
            else:
                logging.warning("Failed to add iptables on %s -> %s: %s / %s", host, dst_ip, o, e)

    # symmetric on dst
    if dst_info and dst_info.get("ssh_user") and dst_info.get("ssh_password"):
        host = dst_info["ip"]
        user = dst_info["ssh_user"]
        pwd = dst_info["ssh_password"]
        bind_ip = dst_info.get("bind_ip")
        check_cmd = f"iptables -C OUTPUT -d {src_ip} -j REJECT"
        rc, out, err = _exec_command_on_host(host, user, pwd, f"sudo -n {check_cmd}", bind_ip=bind_ip, timeout=6)
        if rc == 0:
            logging.info("iptables rule already present on %s -> %s", host, src_ip)
        else:
            ok, o, e = _run_sudo_cmd(host, user, pwd, check_cmd, bind_ip=bind_ip)
            if ok:
                logging.info("Added symmetric iptables REJECT on %s -> %s", host, src_ip)
            else:
                logging.warning("Failed to add symmetric iptables on %s -> %s: %s / %s", host, src_ip, o, e)

    # mark blocked
    conn_blocked[(src_ip, dst_ip)] = True
    conn_blocked[(dst_ip, src_ip)] = True

def remove_block(src_ip: str, dst_ip: str):
    """
    Remove enforced block between src_ip and dst_ip.
    - Remove iptables rules on VMs if present
    - Remove Null0 route on router if present
    """
    src_name, src_info = _find_digital_device_by_ip(src_ip)
    dst_name, dst_info = _find_digital_device_by_ip(dst_ip)

    if src_name == "router" or dst_name == "router":
        target_ip = dst_ip if src_name == "router" else src_ip
        logging.info("Removing Null0 route on digital router for %s", target_ip)
        try:
            _router_ssh_run([f"no ip route {target_ip} 255.255.255.255 Null0"])
            conn_blocked.pop((src_name or src_ip, dst_name or dst_ip), None)
        except Exception as e:
            logging.exception("Failed to remove Null0 route for %s: %s", target_ip, e)
        return

    # remove rule on src
    if src_info and src_info.get("ssh_user") and src_info.get("ssh_password"):
        host = src_info["ip"]
        user = src_info["ssh_user"]
        pwd = src_info["ssh_password"]
        bind_ip = src_info.get("bind_ip")
        rm_cmd = f"iptables -D OUTPUT -d {dst_ip} -j REJECT"
        ok, out, err = _run_sudo_cmd(host, user, pwd, rm_cmd, bind_ip=bind_ip)
        if ok:
            logging.info("Removed iptables REJECT on %s -> %s", host, dst_ip)
        else:
            logging.info("No iptables rule removed (or failed) on %s -> %s: %s", host, dst_ip, err)

    # remove symmetric on dst
    if dst_info and dst_info.get("ssh_user") and dst_info.get("ssh_password"):
        host = dst_info["ip"]
        user = dst_info["ssh_user"]
        pwd = dst_info["ssh_password"]
        bind_ip = dst_info.get("bind_ip")
        rm_cmd = f"iptables -D OUTPUT -d {src_ip} -j REJECT"
        ok, out, err = _run_sudo_cmd(host, user, pwd, rm_cmd, bind_ip=bind_ip)
        if ok:
            logging.info("Removed symmetric iptables REJECT on %s -> %s", host, src_ip)
        else:
            logging.info("No symmetric iptables rule removed (or failed) on %s -> %s: %s", host, src_ip, err)

    conn_blocked.pop((src_ip, dst_ip), None)
    conn_blocked.pop((dst_ip, src_ip), None)

# ---------------- MQTT handlers ----------------
def on_mqtt_connect(client, userdata, flags, rc):
    logging.info("Connected to MQTT broker (rc=%s). Subscribing to health/#", rc)
    prefix = cfg.get("monitor", {}).get("mqtt_prefix", "health")
    client.subscribe(f"{prefix}/#")

def on_mqtt_message(client, userdata, msg):
    try:
        parts = msg.topic.split("/")
        if len(parts) < 3:
            return
        _, src, dst = parts[:3]
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

        prev = conn_reported_status.get(key, True)
        if conn_fail_counts.get(key, 0) >= CONN_FAIL_THRESHOLD and prev:
            conn_reported_status[key] = False
            logging.info("Device-reported connection DOWN %s -> %s", src, dst)
        if conn_success_counts.get(key, 0) >= CONN_RECOVER_THRESHOLD and not prev:
            conn_reported_status[key] = True
            logging.info("Device-reported connection UP %s -> %s", src, dst)
    except Exception as e:
        logging.exception("Error processing MQTT message %s: %s", msg.topic, e)

# ---------------- Decision logic ----------------
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

        if device_fail_counts.get(name, 0) >= DEVICE_FAIL_THRESHOLD:
            if prev is None or prev is True:
                device_status[name] = False
                logging.warning("Device %s declared DOWN by proxy (after %d fails)", name, device_fail_counts[name])
                # stop its corresponding digital node
                if name in digi and digi[name].get("gns3_node_id"):
                    stop_node(digi[name]["gns3_node_id"])
                # block digital-side communications for that digital IP vs others
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

        if device_success_counts.get(name, 0) >= DEVICE_RECOVER_THRESHOLD:
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
            # authoritative proxy: if either device is down -> enforce block on digital side
            if not src_up or not dst_up:
                if src in digi and dst in digi:
                    sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                    if not conn_blocked.get((src, dst), False):
                        add_block(sip, dip)
                        conn_blocked[(src, dst)] = True
                        conn_blocked[(dst, src)] = True
                        logging.info("Blocking digital connection %s->%s due to device DOWN (proxy authoritative)", src, dst)
                continue

            # if device reported connection down, block; else unblock if previously blocked
            if not reported_up:
                if src in digi and dst in digi and not conn_blocked.get((src, dst), False):
                    sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                    add_block(sip, dip)
                    conn_blocked[(src, dst)] = True
                    conn_blocked[(dst, src)] = True
                    logging.info("Blocking digital connection %s->%s (reported by device)", src, dst)
            else:
                if conn_blocked.get((src, dst), False):
                    if src in digi and dst in digi:
                        sip = digi[src]["ip"]; dip = digi[dst]["ip"]
                        remove_block(sip, dip)
                        conn_blocked[(src, dst)] = False
                        conn_blocked[(dst, src)] = False
                        logging.info("Unblocked digital connection %s<->%s (reported recovered)", src, dst)

# ---------------- Main loop ----------------
def main_loop():
    global _running
    logging.info("Starting proxy main loop")
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

# ---------------- Shutdown ----------------
def shutdown(signum=None, frame=None):
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

# ---------------- Entrypoint ----------------
if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if not os.path.exists(CONFIG_FILE):
        logging.error("Config file %s missing. Exiting.", CONFIG_FILE)
        sys.exit(2)

    load_config(CONFIG_FILE)
    start_mqtt_listener()
    main_loop()
