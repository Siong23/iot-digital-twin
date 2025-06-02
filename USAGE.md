# Using the IoT Digital Twin Security Testbed

This guide explains how to use the IoT Digital Twin Security Testbed to simulate attacks in a controlled environment.

## System Components

The testbed consists of several key components:

1. **MQTT Broker**: Simulates IoT device communication
2. **C2 Server**: Command and control server for attack bots
3. **Attack Bots**: Malware-like programs that can compromise vulnerable devices
4. **GNS3 Network**: Virtual network environment for simulating IoT devices

## Running the C2 Server

The C2 server is the central component for managing attack bots. To start it:

```bash
cd AttackBots/c2_server
python c2_server.py
```

This will start the C2 server with:
- Communication server on port 8080
- Web interface on http://localhost:5000

## Registering Attack Bots

Attack bots can connect to the C2 server and register themselves. You can use the provided test script to simulate a bot:

```bash
cd AttackBots/exploit
python test_c2_connection.py
```

For a more complete simulation, use the exploit.py script:

```bash
cd AttackBots/exploit
python exploit.py --c2-host 127.0.0.1 --c2-port 8080
```

## Using the Demo Environment

For testing in a controlled environment without affecting real systems:

```bash
cd AttackBots/exploit
python demo.py
```

This will create a simulated environment with vulnerable devices for testing the attack functionality.

## Launching a DDoS Attack

1. Start the C2 server
2. Register at least one attack bot
3. Navigate to http://localhost:5000/ddos in your browser
4. Select an attack preset or configure a custom attack
5. Click "Launch Attack" to start the DDoS simulation

## Testing Attack Bot Communication

You can test if an attack bot can properly connect to the C2 server using:

```bash
cd AttackBots/exploit
python test_c2_connection.py
```

## Monitoring the System

The web interface provides several monitoring pages:

- **Dashboard**: Overview of system status
- **Bots**: List of compromised devices
- **Credentials**: Harvested login credentials
- **Scans**: Network scan results
- **DDoS**: DDoS attack management

## Security Warning

This system is for educational and research purposes only. Only use it in isolated lab environments and never against real systems or networks.
