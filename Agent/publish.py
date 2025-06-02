import paho.mqtt.client as mqtt

# Define Agent Broker (A)
BROKER_A = {
    'host': '192.168.20.2',
    'port': 1883,
    'username': 'admin',
    'password': 'abc123',
    'topic_subscribe': 'sensors/data',
}

# Define Agent Broker (B)
BROKER_B = {
    'host': '10.10.10.10',
    'port': 1883,
    'username': 'admin',
    'password': 'admin123',
    'topic_publish': 'sensors/digital/data',
}

# Callback for Broker A when connected
def on_connect_broker_a(client, userdata, flags, rc, properties=None, callback_api_version=2.0):
    if rc == 0:
        print("Connected to Agent Broker!")
        # Subscribe to the topic from Broker A
        client.subscribe(BROKER_A['topic_subscribe'])
    else:
        print(f"Failed to connect to Agent Broker, return code {rc}")

# Callback for receiving messages from Broker A
def on_message_broker_a(client, userdata, msg, callback_api_version=2.0):
    print(f"Received message from Agent Broker -> Topic: {msg.topic}, Payload:{msg.payload.decode()}")
    # Publish the received data to Broker B
    broker_b_client.publish(BROKER_B["topic_publish"], msg.payload)
    print(f"Published message to Digital Broker -> Topic: {BROKER_B['topic_publish']}")
    
# Callback for Broker B when connected
def on_connect_broker_b(client, userdata, flags, rc, properties=None, callback_api_version=2.0):
    if rc == 0:
        print("Connected to Digital Broker!")
    else:
        print(f"Failed to connect to Digital Broker, return code {rc}")
        
# Initialize Broker A client (Subscriber)
broker_a_client = mqtt.Client(mqtt.CallbackApiVersion.VERSION1)
broker_a_client.username_pw_set(BROKER_A['username'], BROKER_A['password'])
broker_a_client.on_connect = on_connect_broker_a
broker_a_client.on_message = on_message_broker_a

# Initialize Broker B client (Publisher)
broker_b_client = mqtt.Client(mqtt.CallbackApiVersion.VERSION1)
broker_b_client.username_pw_set(BROKER_B['username'], BROKER_B['password'])
broker_b_client.on_connect = on_connect_broker_b

# Connect to both brokers
print("Connecting to Agent Broker...")
broker_a_client.connect(BROKER_A['host'], BROKER_A['port'])

print("Connecting to Digital Broker...")
broker_b_client.connect(BROKER_B['host'], BROKER_B['port'])

# Start the loop for both clients
broker_b_client.loop_start()    # Start Broker B in a separate thread
broker_a_client.loop_forever()  # Keep Broker A running in the main thread