#!/usr/bin/env python3
"""
broker_agent.py
Run on the broker host (physical or digital).

- Pings sensor and ipcam IPs
- Optionally checks that sensor publishes by subscribing briefly to a configured topic
- Publishes <prefix>/<broker>/<target> messages (default prefix "health")
"""

import time, json, argparse, logging, subprocess
from datetime import datetime
import paho.mqtt.client as mqtt

LOGFILE = "/var/log/broker_agent.log"
logging.basicConfig(filename=LOGFILE, level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")

def ping_once(dest, timeout=2):
    return subprocess.call(
        ["ping", "-c", "1", "-W", str(timeout), dest],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ) == 0

def now_iso():
    return datetime.utcnow().isoformat()

class BrokerAgent:
    def __init__(self, name, peers, mqtt_broker,
                 mqtt_user=None, mqtt_pass=None,
                 interval=10, fail_threshold=3, recover_threshold=3,
                 mqtt_probe_topic=None, prefix="health"):

        self.name = name
        self.peers = peers
        self.mqtt_broker = mqtt_broker
        self.mqtt_user = mqtt_user
        self.mqtt_pass = mqtt_pass
        self.interval = interval
        self.fail_th = fail_threshold
        self.recover_th = recover_threshold
        self.mqtt_probe_topic = mqtt_probe_topic
        self.prefix = prefix.rstrip("/")

        self.fail_counts = {k: 0 for k in peers}
        self.success_counts = {k: 0 for k in peers}
        self.status = {k: True for k in peers}

        # MQTT client (use stable v3 callback signatures)
        self.mqtt = mqtt.Client(client_id=f"broker-agent-{self.name}", protocol=mqtt.MQTTv311)
        if mqtt_user and mqtt_pass:
            self.mqtt.username_pw_set(mqtt_user, mqtt_pass)

        def on_connect(client, userdata, flags, rc):
            logging.info("Connected to MQTT %s with rc=%s", self.mqtt_broker, rc)
        self.mqtt.on_connect = on_connect

        def on_disconnect(client, userdata, rc):
            logging.warning("Disconnected from MQTT %s rc=%s", self.mqtt_broker, rc)
        self.mqtt.on_disconnect = on_disconnect

        try:
            self.mqtt.connect(self.mqtt_broker, 1883, 60)
            self.mqtt.loop_start()
        except Exception as e:
            logging.exception("MQTT connect failed: %s", e)
            raise

    def publish(self, target, state):
        topic = f"{self.prefix}/{self.name}/{target}"
        payload = json.dumps({"status": state, "time": now_iso()})
        try:
            self.mqtt.publish(topic, payload)
            logging.info("Published %s = %s", topic, payload)
        except Exception as e:
            logging.exception("MQTT publish failed: %s", e)

    def mqtt_recent_message(self, topic, timeout=3):
        """Quick subscribe for 'timeout' seconds to see if any message arrives."""
        got = {"ok": False}

        c = mqtt.Client(client_id=f"probe-check-{self.name}", protocol=mqtt.MQTTv311)
        if self.mqtt_user and self.mqtt_pass:
            c.username_pw_set(self.mqtt_user, self.mqtt_pass)

        def on_msg(client, userdata, msg):
            got["ok"] = True
            try:
                client.disconnect()
            except:
                pass

        c.on_message = on_msg

        try:
            c.connect(self.mqtt_broker, 1883, 5)
            c.subscribe(topic)
            c.loop_start()
            t0 = time.time()
            while time.time() - t0 < timeout and not got["ok"]:
                time.sleep(0.2)
        except Exception:
            pass
        finally:
            try:
                c.loop_stop()
                c.disconnect()
            except:
                pass
        return got["ok"]

    def step(self):
        for target, info in self.peers.items():
            ip = info.get("ip")
            ok = ping_once(ip)

            # optional MQTT check
            if not ok and self.mqtt_probe_topic and info.get("check_mqtt"):
                ok = self.mqtt_recent_message(self.mqtt_probe_topic, timeout=3) or ok

            if ok:
                self.fail_counts[target] = 0
                self.success_counts[target] += 1
            else:
                self.success_counts[target] = 0
                self.fail_counts[target] += 1

            prev = self.status[target]
            if self.fail_counts[target] >= self.fail_th and prev:
                self.status[target] = False
                self.publish(target, "DOWN")

            if self.success_counts[target] >= self.recover_th and not prev:
                self.status[target] = True
                self.publish(target, "UP")

    def run_forever(self):
        logging.info("Broker agent started for %s peers=%s prefix=%s",
                     self.name, list(self.peers.keys()), self.prefix)
        while True:
            try:
                self.step()
            except Exception as e:
                logging.exception("Error in step: %s", e)
            time.sleep(self.interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--peers", required=True,
                        help='JSON mapping of peers')
    parser.add_argument("--broker", default="192.168.20.2")
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--fail", type=int, default=3)
    parser.add_argument("--recover", type=int, default=3)
    parser.add_argument("--mqtt-topic", default=None,
                        help="optional topic to check for recent sensor messages (e.g. sensors/physical/data)")
    parser.add_argument("--prefix", default="health", help="topic prefix, e.g. health or digi/health")
    args = parser.parse_args()

    peers = json.loads(args.peers)

    agent = BrokerAgent(
        args.name, peers,
        mqtt_broker=args.broker,
        interval=args.interval,
        fail_threshold=args.fail,
        recover_threshold=args.recover,
        mqtt_probe_topic=args.mqtt_topic,
        prefix=args.prefix
    )
    agent.run_forever()
