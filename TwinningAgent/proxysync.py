#!/usr/bin/env python3
import subprocess
import yaml
import time
import requests
from requests.auth import HTTPBasicAuth

CONFIG_FILE = "devices.yaml"
CHECK_INTERVAL = 30   # seconds

def ping_device(device):
    """Ping device using bind_ip (proxy routing decides phys/digi)."""
    ip = device["ip"]
    bind_ip = device["bind_ip"]
    cmd = ["ping", "-c", "1", "-W", "1", "-I", bind_ip, ip]
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

class GNSSyncAgent:
    def __init__(self, config_file):
        with open(config_file) as f:
            self.cfg = yaml.safe_load(f)
        self.gns3 = self.cfg["gns3"]
        self.devices = self.cfg["devices"]
        self.auth = HTTPBasicAuth(self.gns3["user"], self.gns3["password"])
        self.base_url = self.gns3["url"]
        self.project_id = self.gns3["project_id"]

        # keep state to avoid redundant stop/start
        self.last_state = {}

    def gns3_action(self, node_id, action):
        """Start/stop node in GNS3."""
        url = f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}/{action}"
        r = requests.post(url, auth=self.auth)
        if r.status_code == 200:
            print(f"[GNS3] {action} node {node_id} OK")
        else:
            print(f"[GNS3] {action} node {node_id} FAILED: {r.text}")

    def check_and_sync(self):
        # Only physical devices determine sync
        for name, phys_dev in self.devices["physical"].items():
            node_id = phys_dev.get("gns3_node_id")
            digi_dev = self.devices["digital"].get(name)
            if not node_id or not digi_dev:
                continue

            is_up = ping_device(phys_dev)
            last = self.last_state.get(name)

            if last is None or last != is_up:
                self.last_state[name] = is_up
                if is_up:
                    print(f"[SYNC] Physical {name} UP → starting digital twin")
                    self.gns3_action(node_id, "start")
                else:
                    print(f"[SYNC] Physical {name} DOWN → stopping digital twin")
                    self.gns3_action(node_id, "stop")

    def run(self):
        print("[Agent] Starting proxy sync loop...")
        while True:
            self.check_and_sync()
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    agent = GNSSyncAgent(CONFIG_FILE)
    agent.run()
