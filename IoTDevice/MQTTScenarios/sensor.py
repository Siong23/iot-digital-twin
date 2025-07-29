import RPi.GPIO as GPIO
import serial
import time
import struct
import paho.mqtt.client as mqtt
import json
import socket

# Get the hostname and IP address
hostname = socket.gethostname()
ip = socket.gethostbyname(hostname)
ID = hostname + ip

# MQTT settings
MQTT_BROKER = "192.168.20.2"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/data"

# File containing MQTT credentials (username and password)
CREDENTIALS_FILE = 'mqtt_credentials.txt'

# Function to read credentials from the file
def read_credentials(file_path):
    credentials = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                if line.strip():
                    key, value = line.strip().split(':')
                    credentials[key] = value
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
    return credentials

# Retrieve credentials from the file
credentials = read_credentials(CREDENTIALS_FILE)

# MQTT Authentication (default to None if not found)
MQTT_USERNAME = credentials.get('username', None)
MQTT_PASSWORD = credentials.get('password', None)

# Serial port settings
SERIAL_PORT = "/dev/ttyS0"
BAUD_RATE = 4800

# Initialize MQTT client
client = mqtt.Client()

# Set username and password if available
if MQTT_USERNAME and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
else:
    print("No MQTT username or password found. Proceeding without authentication.")

# Define the on_connect callback
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker successfully")
    else:
        print(f"Failed to connect to MQTT broker, return code {rc}")

client.on_connect = on_connect
client.connect(MQTT_BROKER, MQTT_PORT)

def hex_to_float(hex_value):
    """Convert hexadecimal to float."""
    return struct.unpack('>h', bytes.fromhex(hex_value))[0] * 0.1

def process_data(data):
    """Process the sensor data and return as a dictionary."""
    if len(data) < 8:  # Check if we have enough data
        print("Incomplete data received")
        return None
    return {
        "humidity": hex_to_float(data[3] + data[4]),
        "temperature": hex_to_float(data[5] + data[6]),
    }

def main():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print("Press Ctrl + C to exit")

    try:
        while True:
            hexInput = bytes.fromhex("010300000002C40B")
            ser.write(hexInput)
            time.sleep(0.1)
            buf = []
            while ser.inWaiting():
                buf.append(ser.read().hex())
            if buf:
                print("Raw data:", buf)
                processed_data = process_data(buf)
                if processed_data:
                    print("Processed data:", processed_data)
                    # Publish to MQTT
                    client.publish(MQTT_TOPIC, json.dumps(processed_data))
            else:
                print("No data received")
            time.sleep(5)

    except KeyboardInterrupt:
        print("Program terminated by user")

    finally:
        ser.flush()
        ser.close()
        client.disconnect()

if __name__ == "__main__":
    client.loop_start()
    main()
