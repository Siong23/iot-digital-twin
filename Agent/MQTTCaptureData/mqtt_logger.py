# mqtt_logger.py
import paho.mqtt.client as mqtt
import csv
import json
from datetime import datetime
import signal
import sys

BROKER = {
    'host': 'localhost',
    'port': 1883,
    'username': 'admin',
    'password': 'admin123',
    'topic': 'sensors/digital/data'
}

csv_file = "telemetry_mqtt_log.csv"
client = mqtt.Client()  

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker.")
        client.subscribe(BROKER['topic'])
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        if "temperature" in data and "humidity" in data:
            local_ts = datetime.now()
            sensor_ts = data.get("timestamp", "")
            delay_ms = ""

            if sensor_ts:
                try:
                    delay_ms = (local_ts - datetime.fromisoformat(sensor_ts)).total_seconds() * 1000
                except:
                    sensor_ts = ""
                    delay_ms = ""

            with open(csv_file, "a", newline="") as f:
                writer = csv.writer(f)
                if f.tell() == 0:
                    writer.writerow([
                        "timestamp", "sensor_timestamp", "delay_ms",
                        "temperature", "humidity", "topic", "qos", "retain"
                    ])
                writer.writerow([
                    local_ts.strftime("%Y-%m-%d %H:%M:%S"),
                    sensor_ts,
                    delay_ms,
                    data["temperature"],
                    data["humidity"],
                    msg.topic,
                    msg.qos,
                    msg.retain
                ])
    except:
        pass

def graceful_exit(signum, frame):
    print("Stopping telemetry logger...")
    client.disconnect()
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

client.username_pw_set(BROKER['username'], BROKER['password'])
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER['host'], BROKER['port'])
client.loop_forever()
