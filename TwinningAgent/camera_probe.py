#!/usr/bin/env python3
"""
camera_probe.py / digi_camera_probe.py
Check camera ping + RTSP and publish <prefix>/ipcam/<check>
"""

import time, json, argparse, logging, subprocess
from datetime import datetime
import paho.mqtt.client as mqtt

LOGFILE = "/var/log/camera_probe.log"
logging.basicConfig(filename=LOGFILE, level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def now_iso():
    return datetime.utcnow().isoformat()

def ping_once(ip, timeout=2):
    return subprocess.call(["ping","-c","1","-W",str(timeout), ip],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def ffprobe_check(rtsp_url, timeout=5):
    try:
        cmd = ["ffprobe", "-v", "error", "-rtsp_transport", "tcp", "-t", str(timeout),
               "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", rtsp_url]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout+2)
        return r.returncode == 0 and (r.stdout and r.stdout.strip())
    except Exception:
        return False

def check_rtsp(rtsp_url):
    if ffprobe_check(rtsp_url):
        return True
    try:
        import cv2
        cap = cv2.VideoCapture(rtsp_url)
        ok, _ = cap.read()
        try: cap.release()
        except: pass
        return ok
    except Exception:
        return False

class CameraProbe:
    def __init__(self, cam_ip, rtsp_url, mqtt_broker, mqtt_user=None, mqtt_pass=None,
                 interval=10, fail_threshold=3, recover_threshold=3, prefix="health"):
        self.cam_ip = cam_ip
        self.rtsp_url = rtsp_url
        self.mqtt_broker = mqtt_broker
        self.interval = interval
        self.fail_th = fail_threshold
        self.recover_th = recover_threshold
        self.prefix = prefix.rstrip("/")

        self.mqtt = mqtt.Client(client_id="camera-probe", protocol=mqtt.MQTTv311)
        if mqtt_user and mqtt_pass:
            self.mqtt.username_pw_set(mqtt_user, mqtt_pass)
        self.mqtt.connect(mqtt_broker, 1883, 60)
        self.mqtt.loop_start()
        self.fail_count_ping = 0
        self.success_count_ping = 0
        self.fail_count_rtsp = 0
        self.success_count_rtsp = 0
        self.ping_state = True
        self.rtsp_state = True

    def publish(self, suffix, state):
        topic = f"{self.prefix}/ipcam/{suffix}"
        payload = json.dumps({"status": state, "time": now_iso()})
        try:
            self.mqtt.publish(topic, payload)
            logging.info("Published %s = %s", topic, payload)
        except Exception as e:
            logging.exception("Publish failed: %s", e)

    def step(self):
        ping_ok = ping_once(self.cam_ip)
        rtsp_ok = check_rtsp(self.rtsp_url)

        # ping
        if ping_ok:
            self.fail_count_ping = 0
            self.success_count_ping += 1
        else:
            self.fail_count_ping += 1
            self.success_count_ping = 0

        prev_ping = self.ping_state
        if self.fail_count_ping >= self.fail_th and prev_ping:
            self.ping_state = False
            self.publish("ping", "DOWN")
        if self.success_count_ping >= self.recover_th and not prev_ping:
            self.ping_state = True
            self.publish("ping", "UP")

        # rtsp
        if rtsp_ok:
            self.fail_count_rtsp = 0
            self.success_count_rtsp += 1
        else:
            self.fail_count_rtsp += 1
            self.success_count_rtsp = 0

        prev_rtsp = self.rtsp_state
        if self.fail_count_rtsp >= self.fail_th and prev_rtsp:
            self.rtsp_state = False
            self.publish("rtsp", "DOWN")
        if self.success_count_rtsp >= self.recover_th and not prev_rtsp:
            self.rtsp_state = True
            self.publish("rtsp", "UP")

    def run_forever(self):
        logging.info("Camera probe started for %s (rtsp=%s) prefix=%s", self.cam_ip, self.rtsp_url, self.prefix)
        while True:
            try:
                self.step()
            except Exception as e:
                logging.exception("Error in camera probe step: %s", e)
            time.sleep(self.interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--rtsp", required=True)
    parser.add_argument("--broker", default="192.168.20.2")
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--fail", type=int, default=3)
    parser.add_argument("--recover", type=int, default=3)
    parser.add_argument("--prefix", default="health", help="topic prefix, e.g. health or digi/health")
    args = parser.parse_args()

    cp = CameraProbe(args.ip, args.rtsp, args.broker, interval=args.interval, fail_threshold=args.fail, recover_threshold=args.recover, prefix=args.prefix)
    cp.run_forever()
