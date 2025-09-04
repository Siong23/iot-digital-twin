#!/usr/bin/env python3
"""
sync_status_full.py

Full sync/status + flow enforcement agent (updated with robust IOS verification).

Behavior:
- Ping physical devices (using their bind_ip) and debounce start/stop of digital GNS3 nodes.
- Subscribe to MQTT health/# (no bind) and, with connection debounce, apply flow-blocking:
    * broker/sensor: ssh into the source digital VM and run (exact commands you specified):
        sudo iptables -A OUTPUT -d <VM_IP> -j REJECT   (block)
        sudo iptables -D OUTPUT -d <VM_IP> -j REJECT   (unblock)
    * router: ssh into the digital router and run:
        ip route <VM_IP> 255.255.255.255 Null0         (block)
        no ip route <VM_IP> 255.255.255.255 Null0      (unblock)
  Router changes are verified by reading running-config and RIB to ensure the route is present/absent.
- All SSH connections use the digital device's bind_ip as local source (socket bind).
- Debounce thresholds and iptables chain defaults read from YAML.
"""

import os
import time
import yaml
import json
import socket
import threading
import subprocess
import requests
import logging
import paramiko
import paho.mqtt.client as mqtt
from requests.auth import HTTPBasicAuth

# ---------------- CONFIG ----------------
CONFIG_FILE = "devices.yaml"
PING_COUNT = 1
PING_TIMEOUT = 2

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename="sync_status.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------- HELPERS ----------------
def ping(ip, bind_ip=None):
    """Ping an IP from a specific source IP (uses system ping)."""
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
            method,
            url,
            auth=HTTPBasicAuth(cfg["user"], cfg["password"]),
            timeout=8
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

# ---------------- SOCKET / SSH WITH BIND ----------------
def _socket_with_bind(target_ip, port, bind_ip, timeout=10):
    """
    Create a TCP socket bound to bind_ip (if provided) and connect to target_ip:port.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    if bind_ip:
        try:
            sock.bind((bind_ip, 0))
        except Exception as e:
            logging.error(f"Socket bind error to {bind_ip}: {e}")
            raise
    sock.connect((target_ip, port))
    return sock

def ssh_exec_linux(host_ip, user, password, command, bind_ip=None, timeout=20):
    """
    SSH to a Linux VM via a bound socket and run a non-interactive command.
    Returns (rc, stdout, stderr).
    """
    try:
        # Prepare wrapper for commands with sudo
        if "sudo " in command:
            safe_command = command.replace("sudo ", "", 1)
            full_cmd = f"echo {json.dumps(password)} | sudo -S -p '' bash -lc {json.dumps(safe_command)}"
        else:
            full_cmd = command

        sock = _socket_with_bind(host_ip, 22, bind_ip)
        transport = paramiko.Transport(sock)
        transport.start_client(timeout=timeout)
        transport.auth_password(username=user, password=password)
        session = transport.open_session()
        session.exec_command(full_cmd)
        stdout = session.makefile("r", -1).read()
        stderr = session.makefile_stderr("r", -1).read()
        exit_status = session.recv_exit_status()
        try:
            transport.close()
        except Exception:
            pass
        if exit_status != 0 and stderr:
            logging.warning(f"SSH@{host_ip} stderr: {stderr.strip()}")
        logging.info(f"SSH@{host_ip} ran: {full_cmd}")
        return exit_status, stdout, stderr
    except Exception as e:
        logging.error(f"SSH linux exec error {host_ip} via {bind_ip}: {e}")
        return 1, "", str(e)

# ---------------- Improved IOS SSH helper & verification ----------------
def ssh_exec_ios_commands(host_ip, user, password, enable_password, commands, bind_ip=None, timeout=30, save=False):
    """
    Improved IOS SSH helper.
    - Ensures we are in enable mode by reading the prompt and responding to 'Password:' if necessary.
    - Enters configure terminal and verifies we get a config prompt before sending commands.
    - Returns tuple: (rc, combined_output)
        rc == 0 -> likely success (no IOS error tokens and prompts indicate config mode)
        rc != 0 -> error (include combined_output for debugging)
    """
    try:
        sock = _socket_with_bind(host_ip, 22, bind_ip, timeout=timeout)
        transport = paramiko.Transport(sock)
        transport.start_client(timeout=timeout)
        transport.auth_password(username=user, password=password)

        chan = transport.open_session()
        chan.get_pty()
        chan.invoke_shell()
        chan.settimeout(2.0)

        def recv_all(short_wait=0.12, total_wait=1.2):
            out = ""
            end = time.time() + total_wait
            while time.time() < end:
                try:
                    while chan.recv_ready():
                        out += chan.recv(65535).decode(errors="ignore")
                    time.sleep(short_wait)
                except Exception:
                    break
            return out

        def send_line(line, delay=0.12):
            chan.send(line + "\n")
            time.sleep(delay)

        # initial banner / prompt
        time.sleep(0.08)
        initial = recv_all(total_wait=0.6)

        # Enter enable
        send_line("enable", delay=0.12)
        time.sleep(0.12)
        out1 = recv_all(total_wait=0.8)

        # If device asked for a password or didn't switch to '#' prompt, send enable_password
        if ("Password" in out1 or "password" in out1) or not any(s in out1 for s in ["#", "(config"]):
            send_line(enable_password, delay=0.14)
            time.sleep(0.2)
            out2 = recv_all(total_wait=0.8)
        else:
            out2 = ""

        combined = initial + out1 + out2

        # Check privileged prompt presence (#)
        if "#" not in combined:
            extra = recv_all(total_wait=0.8)
            combined += extra
            if "#" not in combined:
                logging.error(f"Unable to enter enable mode on {host_ip}. Output:\n{combined}")
                try:
                    chan.close()
                    transport.close()
                except Exception:
                    pass
                return 4, combined

        # Enter config terminal
        send_line("terminal length 0", delay=0.08)
        time.sleep(0.08)
        send_line("configure terminal", delay=0.12)
        time.sleep(0.18)
        cfg_out = recv_all(total_wait=0.9)
        combined += cfg_out

        # send each command and capture immediate output
        for c in commands:
            send_line(c, delay=0.12)
            time.sleep(0.14)
            s = recv_all(total_wait=0.4)
            combined += s

        send_line("end", delay=0.12)
        time.sleep(0.12)
        if save:
            send_line("write memory", delay=0.25)
            time.sleep(0.25)
            combined += recv_all(total_wait=0.8)

        combined += recv_all(total_wait=0.6)

        try:
            chan.close()
        except Exception:
            pass
        try:
            transport.close()
        except Exception:
            pass

        ios_error_tokens = [
            "% Invalid input", "% Incomplete", "% Ambiguous",
            "Invalid input detected", "Error:", "Incomplete command", "Unknown command"
        ]
        for tok in ios_error_tokens:
            if tok in combined:
                logging.error(f"IOS returned error token '{tok}' for {host_ip}. Output:\n{combined}")
                return 2, combined

        logging.info(f"SSH IOS@{host_ip} sent {len(commands)} command(s); save={save}")
        return 0, combined

    except Exception as e:
        logging.exception(f"ssh_exec_ios_commands exception for {host_ip} via {bind_ip}: {e}")
        return 3, str(e)

def verify_route_present(host_ip, user, password, enable_password, route_ip, bind_ip=None, timeout=8):
    """
    Verify the route by checking:
      - running-config containing 'ip route <route_ip>'
      - 'show ip route <route_ip>' to see RIB entries
    Returns (present_in_running_config_bool, rib_output, running_config_output)
    """
    present_in_running = False
    run_out = ""
    rib_out = ""
    try:
        sock = _socket_with_bind(host_ip, 22, bind_ip, timeout=timeout)
        transport = paramiko.Transport(sock)
        transport.start_client(timeout=timeout)
        transport.auth_password(username=user, password=password)

        chan = transport.open_session()
        chan.get_pty()
        chan.invoke_shell()

        time.sleep(0.08)
        chan.send("terminal length 0\n")
        time.sleep(0.08)
        cmd1 = f"show running-config | include ip route {route_ip}\n"
        chan.send(cmd1)
        time.sleep(0.35)

        out = ""
        end = time.time() + 1.2
        while time.time() < end:
            try:
                if chan.recv_ready():
                    out += chan.recv(65535).decode(errors="ignore")
                else:
                    time.sleep(0.05)
            except Exception:
                break
        run_out = out

        cmd2 = f"show ip route {route_ip}\n"
        chan.send(cmd2)
        time.sleep(0.35)
        out2 = ""
        end = time.time() + 1.2
        while time.time() < end:
            try:
                if chan.recv_ready():
                    out2 += chan.recv(65535).decode(errors="ignore")
                else:
                    time.sleep(0.05)
            except Exception:
                break
        rib_out = out2

        try:
            chan.close()
        except Exception:
            pass
        try:
            transport.close()
        except Exception:
            pass

        if f"ip route {route_ip} " in run_out:
            present_in_running = True

        return present_in_running, rib_out.strip(), run_out.strip()

    except Exception as e:
        logging.exception(f"verify_route_present exception on {host_ip} via {bind_ip}: {e}")
        return False, str(e), run_out

# ---------------- IPTABLES (exact commands requested) ----------------
def iptables_block_cmd(vm_ip):
    """Exact block command you requested (append to OUTPUT)."""
    return f"sudo iptables -A OUTPUT -d {vm_ip} -j REJECT"

def iptables_unblock_cmd(vm_ip):
    """Exact unblock command you requested (delete rule from OUTPUT)."""
    return f"sudo iptables -D OUTPUT -d {vm_ip} -j REJECT"

# ---------------- DEBOUNCE STATE ----------------
class DebounceState:
    def __init__(self):
        self.state = None  # True=UP, False=DOWN, None=unknown
        self.ok = 0
        self.fail = 0

    def update(self, event_is_up, fail_thres, rec_thres):
        """
        Update counters based on event_is_up.
        Returns:
            True  -> transitioned to UP
            False -> transitioned to DOWN
            None  -> no transition
        """
        if event_is_up:
            self.fail = 0
            self.ok += 1
            if (self.state is False or self.state is None) and self.ok >= rec_thres:
                self.state = True
                self.ok = 0
                return True
        else:
            self.ok = 0
            self.fail += 1
            if (self.state is True or self.state is None) and self.fail >= fail_thres:
                self.state = False
                self.fail = 0
                return False
        return None

# ---------------- FLOW APPLY ----------------
def apply_flow(config, devices_digi, src, dst, new_is_up, conn_states, lock):
    """
    Enforce or remove flow-blocking on the digital *source* device.
    src/dst are names (keys in devices.digital).
    """
    key = (src, dst)
    with lock:
        st = conn_states.setdefault(key, DebounceState())

    mon = config.get("monitor", {})
    fail_th = int(mon.get("connection_fail_threshold", 3))
    rec_th  = int(mon.get("connection_recover_threshold", 3))
    res = st.update(new_is_up, fail_th, rec_th)
    if res is None:
        # no debounced transition
        return

    becoming_up = (res is True)
    becoming_down = (res is False)

    src_digi = devices_digi.get(src)
    dst_digi = devices_digi.get(dst)
    if not src_digi or not dst_digi:
        logging.warning(f"[FLOW] Missing digital twin(s) for {src}->{dst}: src_exists={src_digi is not None}, dst_exists={dst_digi is not None}")
        return

    vm_ip = dst_digi["ip"]   # the peer we want to block/unblock
    src_ip = src_digi["ip"]  # the VM/router we SSH into to enforce
    src_bind = src_digi.get("bind_ip")

    src_type = src.lower()

    if src_type in ("broker", "sensor"):
        user = src_digi.get("ssh_user")
        pw   = src_digi.get("ssh_password")
        if not user or not pw:
            logging.error(f"[FLOW] Missing SSH credentials for {src}. Skipping flow enforcement.")
            return

        if becoming_down:
            cmd = iptables_block_cmd(vm_ip)
        else:
            cmd = iptables_unblock_cmd(vm_ip)

        rc, out, err = ssh_exec_linux(src_ip, user, pw, cmd, bind_ip=src_bind)
        if rc == 0:
            logging.info(f"[FLOW] {src}->{dst}: {'BLOCKED' if becoming_down else 'UNBLOCKED'} on {src} ({src_ip}) via bind {src_bind} (iptables OUTPUT to {vm_ip})")
        else:
            logging.error(f"[FLOW] iptables update failed on {src} ({src_ip}) via bind {src_bind}: rc={rc}, err={err or out}")

    elif src_type == "router":
        # Use router block credentials from top-level 'router' section in YAML
        router_cfg = config.get("router", {})
        user = router_cfg.get("user")
        pw   = router_cfg.get("password")
        en   = router_cfg.get("enable_password", pw)
        save = bool(router_cfg.get("write_meomory", False))

        if not user or not pw:
            logging.error("[FLOW] Missing router credentials in YAML 'router' block. Skipping route enforcement.")
            return

        hostmask = "255.255.255.255"
        if becoming_down:
            cmds = [f"ip route {vm_ip} {hostmask} Null0"]
        else:
            cmds = [f"no ip route {vm_ip} {hostmask} Null0"]

        rc, out = ssh_exec_ios_commands(src_ip, user, pw, en, cmds, bind_ip=src_bind, save=save)
        if rc != 0:
            logging.error(f"[FLOW] Router config action failed on {src_ip} bind {src_bind}; rc={rc}; out:\n{out}")
            return

        # verify presence / absence
        present, rib_out, run_out = verify_route_present(src_ip, user, pw, en, vm_ip, bind_ip=src_bind)
        if becoming_down:
            if present:
                logging.info(f"[FLOW] {src}->{dst}: BLOCKED via router {src} ({src_ip}) bind {src_bind}")
            else:
                logging.error(f"[FLOW] router {src_ip} reported NO host route after issuing 'ip route'. RIB:\n{rib_out}\nRUNCFG:\n{run_out}")
        else:
            if not present:
                logging.info(f"[FLOW] {src}->{dst}: UNBLOCKED via router {src} ({src_ip}) bind {src_bind}")
            else:
                logging.error(f"[FLOW] router {src_ip} still has host route after 'no ip route'. RIB:\n{rib_out}\nRUNCFG:\n{run_out}")

    else:
        logging.info(f"[FLOW] No enforcement configured for device type '{src_type}'")

# ---------------- MQTT CALLBACKS ----------------
def on_message(client, userdata, msg):
    """Handle MQTT health/# messages: topic health/<src>/<dst> with JSON {'status':'UP'|'DOWN'}."""
    try:
        topic_parts = msg.topic.strip().split("/")
        if len(topic_parts) != 3:
            return
        _, src, dst = topic_parts
        payload = json.loads(msg.payload.decode(errors="ignore").strip() or "{}")
        status = payload.get("status")
        if status not in ("UP", "DOWN"):
            return
        new_is_up = (status == "UP")
        logging.info(f"[HEALTH] {src}->{dst}: {status}")
        apply_flow(
            userdata["config"],
            userdata["devices_digi"],
            src, dst, new_is_up,
            userdata["conn_states"],
            userdata["lock"]
        )
    except Exception as e:
        logging.error(f"MQTT on_message exception: {e}")

def start_mqtt(config, devices_digi, conn_states, lock):
    """Start MQTT subscriber. Per instruction: do NOT bind the client's source address."""
    mqtt_cfg = config.get("mqtt", {})
    broker_host = mqtt_cfg.get("host")
    broker_port = int(mqtt_cfg.get("port", 1883))
    broker_user = mqtt_cfg.get("user")
    broker_pass = mqtt_cfg.get("password")

    client = mqtt.Client(userdata={
        "config": config,
        "devices_digi": devices_digi,
        "conn_states": conn_states,
        "lock": lock
    })
    if broker_user:
        client.username_pw_set(broker_user, broker_pass)
    client.on_message = on_message
    client.connect(broker_host, broker_port, keepalive=60)
    topic = f"{config.get('monitor', {}).get('mqtt_prefix', 'health')}/#"
    client.subscribe(topic)
    client.loop_start()
    logging.info(f"MQTT subscriber started to {broker_host}:{broker_port}, topic={topic}")
    return client

# ---------------- MAIN ----------------
def main():
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)

    gns3_cfg = config.get("gns3", {})
    project_id = gns3_cfg.get("project_id")
    devices_phys = config.get("devices", {}).get("physical", {})
    devices_digi = config.get("devices", {}).get("digital", {})
    mon = config.get("monitor", {})

    check_interval = int(mon.get("check_interval_seconds", 60))

    # Debounce states for device power (ping -> start/stop)
    device_states = {name: DebounceState() for name in devices_phys.keys()}
    # Debounce states for connection-level flows (MQTT health)
    conn_states = {}
    lock = threading.Lock()

    # Start MQTT subscriber (per instructions: no bind)
    try:
        start_mqtt(config, devices_digi, conn_states, lock)
    except Exception as e:
        logging.exception(f"Failed to start MQTT subscriber: {e}")
        # continue — ping loop still useful

    dev_fail_th = int(mon.get("device_fail_threshold", 3))
    dev_rec_th  = int(mon.get("device_recover_threshold", 3))

    logging.info("=== Sync agent started ===")
    while True:
        for name, phys in devices_phys.items():
            ip = phys.get("ip")
            bind_ip = phys.get("bind_ip")
            if not ip:
                logging.warning(f"Physical device {name} missing ip in YAML")
                continue

            is_up = ping(ip, bind_ip)
            logging.info(f"[PING] {name} ({ip}) via {bind_ip}: {'UP' if is_up else 'DOWN'}")

            # If there is a digital twin and a GNS3 node_id, manage power with debounce
            digi = devices_digi.get(name)
            if digi:
                node_id = digi.get("gns3_node_id")
                if node_id:
                    st = device_states[name]
                    transition = st.update(is_up, dev_fail_th, dev_rec_th)
                    if transition is True:
                        start_node(gns3_cfg, project_id, node_id)
                        logging.info(f"[POWER] START digital node for {name} after debounce")
                    elif transition is False:
                        stop_node(gns3_cfg, project_id, node_id)
                        logging.info(f"[POWER] STOP digital node for {name} after debounce")

        time.sleep(check_interval)

if __name__ == "__main__":
    main()
