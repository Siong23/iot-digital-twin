import subprocess

def start_mosquitto_sub(host, username, password, topic):
    try:
        # Start the mosquitto_sub process
        process = subprocess.Popen(
            [
                'mosquitto_sub',
                '-h', host,
                '-u', username,
                '-P', password,
                '-t', topic
            ],
            stdout=subprocess.PIPE,     # Capture stdout
            stderr=subprocess.STDOUT,   # Redirect stderr to stdout
            text=True                   # Ensure text mode to output
        )
        print(f"Started mosquitto_sub process with PID: {process.pid}")
        
        # Display the output in real-time
        for line in process.stdout:
            print(line.strip())
            
        return
    except Exception as e:
        print(f"Error starting mosquitto_sub: {e}")
        return None
    
if __name__ == "__main__":
    # MQTT Broker details
    host = 'localhost'
    username = 'admin'
    password = 'admin123'
    topic = 'sensors/data'
    # topic = 'sensors/digital/data'
    
    print(f"Subscribing to MQTT broker {host} on topic '{topic}'... Press Ctrl+C to stop.")
    
    try:
        # Start the subscription process
        start_mosquitto_sub(host, username, password, topic)
    except KeyboardInterrupt:
        print("\nSubscription stopped by user.") 