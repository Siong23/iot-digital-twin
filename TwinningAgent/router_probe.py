#!/usr/bin/env python3
"""
router_probe.py / digi_router_probe.py
Persistent SSH-based router probe (bind to proxy IP).
Publishes <prefix>/router/<target>
Requires: paramiko, paho-mqtt
"""

import argparse, socket, time, json, logging, sys
from datetime import datetime

import paramiko
import paho.mqtt.client as mqtt

LOGFILE = "/var/log/router_probe.log"
logging.basicConfig(filename=LOGFILE, level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def now_iso():
    return datetime.utcnow().isoformat()

class RouterProbe:
    def __init__(self, host, username, password, peers, mqtt_broker, bind_ip=None,
                 interval=10, fail=3, recover=3, ping_repeat=3, ping_timeout=2, keepalive=10, prefix="health"):
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
        self.prefix = prefix.rstrip("/")

        # MQTT publisher
        self.mqtt = mqtt.Client(client_id="router-probe", protocol=mqtt.MQTTv311)
        try:
            self.mqtt.connect(mqtt_broker, 1883, 60)
            self.mqtt.loop_start()
        except Exception as e:
            logging.exception("MQTT connect error: %s", e)
            raise

        # state
        self.fail_counts = {k: 0 for k in peers}
        self.success_counts = {k: 0 for k in peers}
        self.status = {k: True for k in peers}

        # SSH transport (Paramiko) - persistent
        self.transport = None
        self.last_connect_time = 0

    def publish(self, target, state):
        topic = f"{self.prefix}/router/{target}"
        payload = json.dumps({"status": state, "time": now_iso()})
        try:
            self.mqtt.publish(topic, payload)
            logging.info("Published %s -> %s", topic, payload)
        except Exception as e:
            logging.exception("MQTT publish failed: %s", e)

    def _open_transport(self, timeout=10):
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
        transport.auth_password(self.username, self.password)
        transport.set_keepalive(self.keepalive)
        self.transport = transport
        self.last_connect_time = time.time()

    def _close_transport(self):
        try:
            if self.transport:
                try:
                    self.transport.close()
                except:
                    pass
        finally:
            self.transport = None

    def _ensure_transport(self):
        if self.transport is not None and self.transport.is_active():
            return True
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
        if not self._ensure_transport():
            return False, ""

        try:
            chan = self.transport.open_session()
            cmd = f"ping {dest_ip} repeat {self.ping_repeat} timeout {self.ping_timeout}"
            chan.exec_command(cmd)
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
            try:
                chan.close()
            except:
                pass

            ok = False
            if "Success rate is" in out_text:
                try:
                    import re
                    m = re.search(r"Success rate is\s+(\d+)\s+percent", out_text)
                    if m and int(m.group(1)) > 0:
                        ok = True
                except Exception:
                    pass
            if not ok and "!" in out_text:
                ok = True
            lower = out_text.lower()
            if not ok and ("reply" in lower or "bytes from" in lower):
                ok = True

            logging.debug("Ping %s -> output: %s", dest_ip, out_text.replace('\n', ' | '))
            return ok, out_text
        except Exception as e:
            logging.exception("Error running ping on router: %s", e)
            try:
                self._close_transport()
            except:
                pass
            return False, ""

    def step(self):
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
            if self.fail_counts[name] >= self.fail_threshold and prev:
                self.status[name] = False
                logging.warning("Router reports %s DOWN (after %d fails)", name, self.fail_counts[name])
                self.publish(name, "DOWN")
            if self.success_counts[name] >= self.recover_threshold and not prev:
                self.status[name] = True
                logging.info("Router reports %s UP (after %d successes)", name, self.success_counts[name])
                self.publish(name, "UP")

    def run_forever(self):
        try:
            logging.info("RouterProbe started (host=%s bind=%s prefix=%s)", self.host, self.bind_ip, self.prefix)
            self._ensure_transport()
            while True:
                try:
                    self.step()
                except Exception as e:
                    logging.exception("Error in step: %s", e)
                time.sleep(self.interval)
        finally:
            try:
                self._close_transport()
            except:
                pass

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--user", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--peers", required=True)
    p.add_argument("--broker", required=True)
    p.add_argument("--bind-ip", default=None)
    p.add_argument("--interval", type=int, default=10)
    p.add_argument("--fail", type=int, default=3)
    p.add_argument("--recover", type=int, default=3)
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--timeout", type=int, default=2)
    p.add_argument("--keepalive", type=int, default=10)
    p.add_argument("--prefix", default="health", help="topic prefix, e.g. health or digi/health")
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
        keepalive=args.keepalive,
        prefix=args.prefix
    )
    rp.run_forever()
