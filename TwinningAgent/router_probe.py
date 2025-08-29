#!/usr/bin/env python3
"""
router_probe.py
Run on proxy. SSH to Cisco router (bound to phys IP) and run 'ping' from router's shell to peers.
Requires paramiko + paho-mqtt
"""

import time, json, argparse, logging, socket
from datetime import datetime
import paramiko
import paho.mqtt.client as mqtt

LOGFILE="/var/log/router_probe.log"
logging.basicConfig(filename=LOGFILE, level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def now_iso(): return datetime.utcnow().isoformat()

class RouterProbe:
    def __init__(self, host, username, password, peers, mqtt_broker, bind_ip=None, interval=10, fail=3, recover=3):
        self.host = host
        self.username = username
        self.password = password
        self.peers = peers
        self.bind_ip = bind_ip
        self.interval = interval
        self.fail = fail
        self.recover = recover
        self.fail_counts = {k:0 for k in peers}
        self.success_counts = {k:0 for k in peers}
        self.status = {k: True for k in peers}
        self.mqtt = mqtt.Client(client_id="router-probe", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt.connect(mqtt_broker, 1883, 60)
        self.mqtt.loop_start()

    def publish(self, target, state):
        topic = f"health/router/{target}"
        payload = json.dumps({"status": state, "time": now_iso()})
        try:
            self.mqtt.publish(topic, payload)
            logging.info("Published %s -> %s", topic, payload)
        except Exception as e:
            logging.exception("Publish failed: %s", e)

    def ssh_connect(self):
        """Open paramiko SSH connection bound to self.bind_ip"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.bind_ip:
            sock.bind((self.bind_ip, 0))  # bind to proxy's physical IP
        sock.settimeout(5)
        sock.connect((self.host, 22))

        transport = paramiko.Transport(sock)
        transport.start_client()
        transport.auth_password(username=self.username, password=self.password)
        chan = transport.open_session()
        chan.get_pty()
        chan.invoke_shell()
        return transport, chan

    def ping_from_router(self, dest):
        transport, chan = None, None
        try:
            transport, chan = self.ssh_connect()
            # send ping command
            cmd = f"ping {dest} repeat 3\n"
            chan.send(cmd)
            time.sleep(3)  # wait for output
            output = ""
            while chan.recv_ready():
                output += chan.recv(1024).decode(errors="ignore")
            ok = ("Success rate is" in output and "0 percent" not in output) or ("!" in output)
            return ok
        except Exception as e:
            logging.exception("Router SSH ping failed: %s", e)
            return False
        finally:
            if chan: chan.close()
            if transport: transport.close()

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)  # router IP
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--peers", required=True, help='JSON mapping of peers')
    parser.add_argument("--broker", default="192.168.20.2")
    parser.add_argument("--bind-ip", default=None, help="Bind to this local IP to force physical path")
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--fail", type=int, default=3)
    parser.add_argument("--recover", type=int, default=3)
    args = parser.parse_args()

    peers = json.loads(args.peers)
    rp = RouterProbe(args.host, args.user, args.password, peers,
                     mqtt_broker=args.broker,
                     bind_ip=args.bind_ip,
                     interval=args.interval,
                     fail=args.fail, recover=args.recover)
    rp.run_forever()
