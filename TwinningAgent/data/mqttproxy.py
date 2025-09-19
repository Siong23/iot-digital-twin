import json
from datetime import datetime
import paho.mqtt.client as mqtt

# -------- CONFIGURATION --------
# Physical Broker (on physical network via ens4)
BROKER_PHYS = {
    'host': '192.168.20.2',  
    'port': 1883,
    'username': 'admin',
    'password': 'admin123',
    'topic_subscribe': 'sensors/data'
}

# Digital Sensors Broker (on digital network via ens5)
BROKER_DIGI = {
    'host': '192.168.254.10',  
    'port': 1883,
    'username': 'admin',
    'password': 'admin123',
    'topic_publish': 'sensors/digital/data'
}

# -------- CALLBACKS --------
def on_connect_phys(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to Physical Broker")
        client.subscribe(BROKER_PHYS['topic_subscribe'])
    else:
        print("Failed to connect to Physical Broker", rc)

def on_message_phys(client, userdata, msg):
    print(f"Physical -> Topic: {msg.topic}, Payload: {msg.payload.decode()}")
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print("Invalid JSON, skipping.")
        return

    # Add timestamp & source info
    payload["timestamp"] = datetime.utcnow().isoformat()
    payload["source"] = "physical"

    # Publish to digital broker
    enriched_payload = json.dumps(payload)
    digi_client.publish(BROKER_DIGI['topic_publish'], enriched_payload)
    print(f"Forwarded to Digital Broker: {BROKER_DIGI['topic_publish']}")

def on_connect_digi(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to Digital Broker")
    else:
        print("Failed to connect to Digital Broker", rc)

# -------- SETUP --------
phys_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
phys_client.username_pw_set(BROKER_PHYS['username'], BROKER_PHYS['password'])
phys_client.on_connect = on_connect_phys
phys_client.on_message = on_message_phys

digi_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
digi_client.username_pw_set(BROKER_DIGI['username'], BROKER_DIGI['password'])
digi_client.on_connect = on_connect_digi

# Connect
digi_client.connect(BROKER_DIGI['host'], BROKER_DIGI['port'], bind_address="192.168.10.253")
phys_client.connect(BROKER_PHYS['host'], BROKER_PHYS['port'], bind_address="192.168.10.254")

# Start both loops
digi_client.loop_start()
phys_client.loop_forever()
