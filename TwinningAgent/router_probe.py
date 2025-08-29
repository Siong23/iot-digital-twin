#!/usr/bin/env python3
"""
router_probe.py
Persistent SSH-based router probe (bind to proxy IP).
- Reuses one Paramiko Transport (keepalive)
- Runs 'ping <ip> repeat <count> timeout <sec>' on router
- Publishes health/router/<target> -> {"status":"UP"/"DOWN","time":"..."}
- Debounce using fail/recover thresholds
Requires: paramiko, paho-mqtt
"""

import argparse
import socket
import time
import json
import logging
import sys
from datetime import datetime

import paramiko
import paho.mqtt.client as mqtt

LOGFILE = "/var/log/router_probe.log"
logging.basicConfig(filename=LOGFILE,
                    level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")

def now_iso():
    return datetime.utcnow().isoformat()

class RouterProbe:
    def __init__(self, host, username, password, peers, mqtt_broker,
                 bind_ip=None, interval=10, fail=3, recover=3,
                 ping_repeat=3, ping_timeout=2, keepalive=10):
        """
        peers: dict: {name: {"ip":"x.x.x.x"}, ...}
        """
        self.host = host
        self.username = username
        self.password = password
        self.peers = peers
        self.bind_ip = bind_ip
        self.interval = interval
        self.fail_threshold = fail
        self.recover_threshold = recover
        self.ping_repeat = ping_repeat
        self.ping_timeout = ping_timeout
        self.keepalive = keepalive

        # MQTT publisher
        self.mqtt = mqtt.Client(client_id="router-probe")
        try:
            self.mqtt.connect(mqtt_broker, 1883, 60)
            self.mqtt.loop_start()
        except Exception as e:
            logging.exception("MQTT connect error: %s", e)
            raise

        # state
        self.fail_counts = {k: 0 for k in peers}
        self.success_counts = {k: 0 for k in peers}
        self.status = {k: True for k in peers}  # assume UP initially

        # SSH transport (Paramiko) - persistent
        self.transport = None
        self.last_connect_time = 0

    def publish(self, target, state):
        topic = f"health/router/{target}"
        payload = json.dumps({"status": state, "time": now_iso()})
        try:
            self.mqtt.publish(topic, payload)
            logging.info("Published %s -> %s", topic, payload)
        except Exception as e:
            logging.exception("MQTT publish failed: %s", e)

    def _open_transport(self, timeout=10):
        """Open persistent Paramiko Transport over a pre-bound socket."""
        logging.info("Opening SSH transport to %s (bind=%s)", self.host, self.bind_ip)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.bind_ip:
            try:
                sock.bind((self.bind_ip, 0))
            except Exception as e:
                logging.exception("Failed to bind socket to %s: %s", self.bind_ip, e)
                sock.close()
                raise
        sock.settimeout(timeout)
        sock.connect((self.host, 22))

        transport = paramiko.Transport(sock)
        transport.start_client(timeout=timeout)
        # Use password auth; adjust for keys if needed
        transport.auth_password(self.username, self.password)
        transport.set_keepalive(self.keepalive)
        logging.info("SSH transport established")
        self.transport = transport
        self.last_connect_time = time.time()

    def _close_transport(self):
        try:
            if self.transport:
                logging.info("Closing SSH transport")
                try:
                    self.transport.close()
                except Exception:
                    pass
        finally:
            self.transport = None

    def _ensure_transport(self):
        """Ensure persistent transport is available; reconnect with backoff on failure."""
        if self.transport is not None and self.transport.is_active():
            return True
        # attempt reconnect with simple backoff
        backoff = 1
        for attempt in range(1, 6):
            try:
                self._open_transport()
                return True
            except Exception as e:
                logging.warning("SSH connect attempt %d failed: %s", attempt, e)
                time.sleep(backoff)
                backoff = min(backoff * 2, 10)
        logging.error("Failed to establish SSH transport after retries")
        return False

    def _run_ping_on_router(self, dest_ip):
        """
        Run ping from router via transport.
        Uses a new session/channel per command (exec_command style).
        Returns (success_bool, raw_output)
        """
        if not self._ensure_transport():
            return False, ""

        try:
            chan = self.transport.open_session()
            # construct IOS ping command
            # 'ping <ip> repeat <n> timeout <sec>'
            cmd = f"ping {dest_ip} repeat {self.ping_repeat} timeout {self.ping_timeout}"
            chan.exec_command(cmd)
            # read output until exit_status_ready or timeout
            timeout = self.ping_repeat * (self.ping_timeout + 1) + 5
            start = time.time()
            output = b""
            while True:
                if chan.recv_ready():
                    output += chan.recv(4096)
                if chan.exit_status_ready():
                    break
                if time.time() - start > timeout:
                    logging.warning("Ping command timeout for %s", dest_ip)
                    break
                time.sleep(0.05)
            try:
                out_text = output.decode(errors="ignore")
            except Exception:
                out_text = str(output)
            # close channel
            try:
                chan.close()
            except Exception:
                pass

            # Determine success:
            # Cisco output often contains "Success rate is X percent (Y/X)" or '!' marks.
            ok = False
            if "Success rate is" in out_text:
                try:
                    # extract percent
                    idx = out_text.find("Success rate is")
                    snippet = out_text[idx: idx + 60]
                    # find number before 'percent'
                    import re
                    m = re.search(r"Success rate is\s+(\d+)\s+percent", snippet)
                    if m and int(m.group(1)) > 0:
                        ok = True
                except Exception:
                    pass
            if not ok:
                # fallback: check for '!' or '!' lines (exclamation mark indicates reply)
                if "!" in out_text:
                    ok = True
                # also some IOS versions print '!!!' etc.
                if "!" not in out_text and "Success rate is" not in out_text:
                    # try to look for 'Reply' or 'bytes from'
                    lower = out_text.lower()
                    if "reply" in lower or "bytes from" in lower:
                        ok = True

            logging.debug("Ping %s -> output: %s", dest_ip, out_text.replace('\n', ' | '))
            return ok, out_text
        except Exception as e:
            logging.exception("Error running ping on router: %s", e)
            # on fatal transport error, close so next loop reconnects
            try:
                self._close_transport()
            except:
                pass
            return False, ""

    def step(self):
        """One monitoring iteration across all peers."""
        for name, info in self.peers.items():
            ip = info.get("ip")
            ok, raw = self._run_ping_on_router(ip)
            if ok:
                self.fail_counts[name] = 0
                self.success_counts[name] += 1
            else:
                self.success_counts[name] = 0
                self.fail_counts[name] += 1

            prev = self.status.get(name, True)
            # declare DOWN
            if self.fail_counts[name] >= self.fail_threshold and prev:
                self.status[name] = False
                logging.warning("Router reports %s DOWN (after %d fails)", name, self.fail_counts[name])
                self.publish(name, "DOWN")
            # declare RECOVERED
            if self.success_counts[name] >= self.recover_threshold and not prev:
                self.status[name] = True
                logging.info("Router reports %s UP (after %d successes)", name, self.success_counts[name])
                self.publish(name, "UP")

    def run_forever(self):
        try:
            logging.info("RouterProbe started (host=%s bind=%s)", self.host, self.bind_ip)
            # initial ensure transport (attempt)
            self._ensure_transport()
            while True:
                try:
                    self.step()
                except Exception as e:
                    logging.exception("Error in step: %s", e)
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logging.info("RouterProbe received keyboard interrupt, exiting")
        finally:
            # cleanup
            try:
                self.mqtt.loop_stop()
            except:
                pass
            self._close_transport()

def parse_args():
    p = argparse.ArgumentParser(description="Router probe (persistent SSH, bind source IP)")
    p.add_argument("--host", required=True, help="router IP")
    p.add_argument("--user", required=True, help="router SSH user")
    p.add_argument("--password", required=True, help="router SSH password")
    p.add_argument("--peers", required=True, help='JSON mapping of peers: {"broker":{"ip":"x.x.x.x"},...}')
    p.add_argument("--broker", required=True, help="MQTT broker IP")
    p.add_argument("--bind-ip", default=None, help="local source IP to bind socket to (proxy physical path)")
    p.add_argument("--interval", type=int, default=10)
    p.add_argument("--fail", type=int, default=3)
    p.add_argument("--recover", type=int, default=3)
    p.add_argument("--repeat", type=int, default=3, help="ping repeat count")
    p.add_argument("--timeout", type=int, default=2, help="ping timeout (router cmd)")
    p.add_argument("--keepalive", type=int, default=10, help="ssh transport keepalive seconds")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    try:
        peers = json.loads(args.peers)
    except Exception as e:
        print("Failed to parse peers JSON:", e)
        sys.exit(2)

    rp = RouterProbe(
        host=args.host,
        username=args.user,
        password=args.password,
        peers=peers,
        mqtt_broker=args.broker,
        bind_ip=args.bind_ip,
        interval=args.interval,
        fail=args.fail,
        recover=args.recover,
        ping_repeat=args.repeat,
        ping_timeout=args.timeout,
        keepalive=args.keepalive
    )
    rp.run_forever()
