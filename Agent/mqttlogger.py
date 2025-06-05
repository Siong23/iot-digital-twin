import paho.mqtt.client as mqtt
import csv
import json
from datetime import datetime

# MQTT Broker Configuration (localhost with authentication)
BROKER = {
    'host': 'localhost',
    'port': 1883,
    'username': 'admin',
    'password': 'abc123',
    'topic': 'sensors/data'
    # 'password': 'admin123',
    # 'topic': 'sensors/digital/data'
}

# CSV File
csv_file = "telemetry_log.csv"

# Callback when connected to the MQTT broker
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker.")
        client.subscribe(BROKER['topic'])
    else:
        print(f"Connection failed with code {rc}")

# Callback when a message is received
def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"Received: {payload}")
    try:
        data = json.loads(payload)
        if "temperature" in data and "humidity" in data:
            temperature = data["temperature"]
            humidity = data["humidity"]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(csv_file, "a", newline="") as f:
                writer = csv.writer(f)
                if f.tell() == 0:
                    writer.writerow(["timestamp", "temperature", "humidity"])
                writer.writerow([timestamp, temperature, humidity])
                print(f"Logged data: {timestamp}, {temperature}, {humidity}")
        else:
            print("Required keys not found in JSON payload")

    except json.JSONDecodeError:
        print("Payload is not valid JSON, skipping")

# Set up MQTT client
client = mqtt.Client()
client.username_pw_set(BROKER['username'], BROKER['password'])
client.on_connect = on_connect
client.on_message = on_message

# Connect and run
try:
    client.connect(BROKER['host'], BROKER['port'])
    client.loop_forever()
except Exception as e:
    print(f"MQTT connection error: {e}")
