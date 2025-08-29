#!/usr/bin/env python3
"""
router_probe.py
Run on proxy. SSH to Cisco router and run 'ping' from router's shell to peers.
Requires netmiko.
"""
import time, json, argparse, logging
from datetime import datetime
from netmiko import ConnectHandler
import paho.mqtt.client as mqtt

LOGFILE="/var/log/router_probe.log"
logging.basicConfig(filename=LOGFILE, level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def now_iso(): return datetime.utcnow().isoformat()

class RouterProbe:
    def __init__(self, host_alias, username, password, peers, mqtt_broker, interval=10, fail=3, recover=3):
        self.host_alias = host_alias
        self.username = username
        self.password = password
        self.peers = peers
        self.interval = interval
        self.fail = fail
        self.recover = recover
        self.fail_counts = {k:0 for k in peers}
        self.success_counts = {k:0 for k in peers}
        self.status = {k: True for k in peers}
        self.mqtt = mqtt.Client("router-probe")
        self.mqtt.connect(mqtt_broker, 1883, 60)
        self.mqtt.loop_start()

    def publish(self, target, state):
        topic = f"health/router/{target}"
        payload = json.dumps({"status": state, "time": now_iso()})
        try:
            self.mqtt.publish(topic, payload)
            logging.info("Published %s", payload)
        except Exception as e:
            logging.exception("Publish failed: %s", e)

    def ping_from_router(self, dest):
        conn = None
        try:
            device = {
                "device_type": "cisco_ios",
                "host": self.host_alias,   # can be IP if using password auth
                "username": self.username,
                "password": self.password,
                "secret": self.password,
                "fast_cli": False
            }
            conn = ConnectHandler(**device)
            conn.enable()
            # use 3 pings (change as needed)
            out = conn.send_command(f"ping {dest} repeat 3", expect_string=r"#", strip_prompt=True, strip_command=True)
            # crude success detection: look for 'Success rate is' or '!!!' or 'Success rate is 0 percent'
            ok = ("Success rate is" in out and "0 percent" not in out) or ("!" in out)
            return ok
        except Exception as e:
            logging.exception("Router SSH ping failed: %s", e)
            return False
        finally:
            if conn:
                try:
                    conn.disconnect()
                except:
                    pass

    def step(self):
        for target, info in self.peers.items():
            ip = info.get("ip")
            ok = self.ping_from_router(ip)
            if ok:
                self.fail_counts[target]=0; self.success_counts[target]+=1
            else:
                self.success_counts[target]=0; self.fail_counts[target]+=1

            prev = self.status[target]
            if self.fail_counts[target] >= self.fail and prev:
                self.status[target] = False
                self.publish(target, "DOWN")
            if self.success_counts[target] >= self.recover and not prev:
                self.status[target] = True
                self.publish(target, "UP")

    def run_forever(self):
        while True:
            try:
                self.step()
            except Exception as e:
                logging.exception("Step error: %s", e)
            time.sleep(self.interval)

if __name__ == "__main__":
    # example usage: set host alias in ~/.ssh/config or set host to router IP accessible from proxy
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)  # host/ip
    parser.add_argument("--user", required=True)
    parser.add_argument("--pass", required=True)
    parser.add_argument("--peers", required=True, help='JSON mapping of peers')
    parser.add_argument("--broker", default="192.168.20.2")
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--fail", type=int, default=3)
    parser.add_argument("--recover", type=int, default=3)
    args = parser.parse_args()

    peers = json.loads(args.peers)
    rp = RouterProbe(args.host, args.user, args.pass, peers, mqtt_broker=args.broker, interval=args.interval, fail=args.fail, recover=args.recover)
    rp.run_forever()
