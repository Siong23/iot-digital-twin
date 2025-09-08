#!/usr/bin/env python3
"""
sensor_agent.py
Pings peers, optionally checks MQTT, publishes <prefix>/<sensor>/<target>
"""

import time, json, argparse, logging, subprocess
from datetime import datetime
import paho.mqtt.client as mqtt

DEFAULT_BROKER = "192.168.20.2"
DEFAULT_INTERVAL = 10
DEFAULT_FAIL_THRESHOLD = 3
DEFAULT_RECOVER_THRESHOLD = 3
LOGFILE = "/var/log/sensor_agent.log"
logging.basicConfig(filename=LOGFILE, level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def ping_once(dest, bind_ip=None, timeout=2):
    cmd = ["ping", "-c", "1", "-W", str(timeout)]
    if bind_ip:
        cmd.extend(["-I", bind_ip])
    cmd.append(dest)
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def now_iso():
    return datetime.utcnow().isoformat()

class HealthAgent:
    def __init__(self, name, peers, mqtt_broker, mqtt_user=None, mqtt_pass=None,
                 bind_ip=None, interval=DEFAULT_INTERVAL,
                 fail_threshold=DEFAULT_FAIL_THRESHOLD, recover_threshold=DEFAULT_RECOVER_THRESHOLD,
                 check_mqtt_topic=None, prefix="health"):
        self.name = name
        self.peers = peers
        self.mqtt_broker = mqtt_broker
        self.mqtt_user = mqtt_user
        self.mqtt_pass = mqtt_pass
        self.bind_ip = bind_ip
        self.interval = interval
        self.fail_th = fail_threshold
        self.recover_th = recover_threshold
        self.check_mqtt_topic = check_mqtt_topic
        self.prefix = prefix.rstrip("/")

        self.fail_counts = {k:0 for k in peers}
        self.success_counts = {k:0 for k in peers}
        self.status = {k: True for k in peers}

        self.mqtt = mqtt.Client(client_id=f"sensor-agent-{self.name}", protocol=mqtt.MQTTv311)
        if mqtt_user and mqtt_pass:
            self.mqtt.username_pw_set(mqtt_user, mqtt_pass)
        self.mqtt.connect(self.mqtt_broker, 1883, 60)
        self.mqtt.loop_start()

    def publish(self, target, state):
        topic = f"{self.prefix}/{self.name}/{target}"
        payload = json.dumps({"status": state, "time": now_iso()})
        try:
            self.mqtt.publish(topic, payload, qos=0, retain=False)
            logging.info("Published %s = %s", topic, payload)
        except Exception as e:
            logging.exception("MQTT publish failed: %s", e)

    def optional_mqtt_check(self, topic, timeout_s=3):
        received = {"ok": False}
        client = mqtt.Client(client_id=f"sensor-agent-check-{self.name}", protocol=mqtt.MQTTv311)
        if self.mqtt_user and self.mqtt_pass:
            client.username_pw_set(self.mqtt_user, self.mqtt_pass)
        def on_message(c, userdata, msg):
            try:
                received["ok"] = True
            except:
                pass
            finally:
                try:
                    c.disconnect()
                except:
                    pass
        client.on_message = on_message
        try:
            client.connect(self.mqtt_broker, 1883, 5)
            client.subscribe(topic)
            client.loop_start()
            t0 = time.time()
            while time.time() - t0 < timeout_s and not received["ok"]:
                time.sleep(0.2)
        except Exception:
            pass
        finally:
            try:
                client.loop_stop()
                client.disconnect()
            except:
                pass
        return received["ok"]

    def check_peer(self, target_name, target_info):
        ip = target_info.get("ip")
        ok = ping_once(ip, bind_ip=self.bind_ip)
        if not ok and target_info.get("check_mqtt"):
            topic = target_info.get("mqtt_probe_topic")
            if topic:
                ok = self.optional_mqtt_check(topic, timeout_s=3) or ok
        return ok

    def step(self):
        for target_name, info in self.peers.items():
            ok = self.check_peer(target_name, info)
            if ok:
                self.fail_counts[target_name] = 0
                self.success_counts[target_name] += 1
            else:
                self.success_counts[target_name] = 0
                self.fail_counts[target_name] += 1

            prev = self.status[target_name]
            if self.fail_counts[target_name] >= self.fail_th and prev:
                self.status[target_name] = False
                self.publish(target_name, "DOWN")
            if self.success_counts[target_name] >= self.recover_th and not prev:
                self.status[target_name] = True
                self.publish(target_name, "UP")

    def run_forever(self):
        logging.info("Sensor agent %s started peers=%s prefix=%s", self.name, list(self.peers.keys()), self.prefix)
        while True:
            try:
                self.step()
            except Exception as e:
                logging.exception("Error in step: %s", e)
            time.sleep(self.interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="device name (sensor)")
    parser.add_argument("--peers", required=True,
                        help="JSON string of peers: {\"broker\":{\"ip\":\"192.168.20.2\",\"check_mqtt\":false}, ...}")
    parser.add_argument("--broker", default=DEFAULT_BROKER, help="MQTT broker IP")
    parser.add_argument("--bind-ip", default=None, help="optional source IP to bind ping from")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    parser.add_argument("--fail", type=int, default=DEFAULT_FAIL_THRESHOLD)
    parser.add_argument("--recover", type=int, default=DEFAULT_RECOVER_THRESHOLD)
    parser.add_argument("--prefix", default="health", help="topic prefix, e.g. health or digi/health")
    args = parser.parse_args()

    peers = json.loads(args.peers)
    agent = HealthAgent(args.name, peers, mqtt_broker=args.broker, mqtt_user=None, mqtt_pass=None,
                        bind_ip=args.bind_ip, interval=args.interval,
                        fail_threshold=args.fail, recover_threshold=args.recover,
                        check_mqtt_topic=None, prefix=args.prefix)
    agent.run_forever()
