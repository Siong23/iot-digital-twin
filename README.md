# IoT Digital Twin Security Testbed for GNS3

## Overview

This repository provides a comprehensive IoT digital twin environment for security testing and research using GNS3. The project enables researchers and security professionals to simulate IoT networks, deploy attack vectors, and analyze vulnerabilities in a controlled environment.

The IoT Digital Twin Security Testbed allows you to:
- Create realistic IoT network topologies in GNS3
- Deploy MQTT-based communication between IoT devices
- Simulate various attack scenarios (DDoS, credential harvesting, etc.)
- Test security measures and defensive strategies
- Analyze network traffic patterns in a controlled environment

## Repository Structure

```
├── Agent/                  # IoT device agents
│   ├── mqttbroker.py       # MQTT broker implementation
│   └── publish.py          # MQTT publishing utilities
├── AttackBots/             # Attack simulation tools
│   ├── c2_server/          # Command & Control server
│   │   ├── c2_server.py    # Main C2 server implementation
│   │   └── ...             # Supporting modules
│   └── exploit/            # Exploitation tools
│       ├── exploit.py      # Main exploit framework
│       └── ...             # Various attack modules
├── README.md               # Main project documentation
├── USAGE.md                # Detailed usage instructions
└── .gitignore              # Git ignore configuration
```

## Prerequisites

- **OS**: Ubuntu 22.04.4 LTS (recommended)
- **Hardware Requirements**:
  - CPU with KVM support
  - Minimum 8GB RAM (16GB+ recommended)
  - 50GB+ free disk space
- **Software Dependencies**:
  - GNS3 (installed on Linux)
  - Docker
  - Python 3 with python3-venv package
  - make, wget, konsole
  - Cisco 7200 router GNS3 image
  - Open vSwitch
  - Ubuntu Server image
  - Ubuntu Guest Additions
  - Kali Linux for GNS3
  - TightVNC

## Installation & Setup

### 1. Setting up the Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/iot-digital-twin.git
cd iot-digital-twin

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Setting up the MQTT Broker

The MQTT broker serves as the communication backbone for IoT devices in the testbed.

```bash
# Install dependencies
cd Agent
pip install paho-mqtt

# Start the MQTT broker
python mqttbroker.py
```

### 3. Setting up the Attack System

```bash
# Install C2 server dependencies
cd ../AttackBots/c2_server
pip install -r requirements.txt

# Install exploit framework dependencies
cd ../exploit
pip install -r requirements.txt
```

#### Troubleshooting Installation

If you encounter pip installation errors with requirements.txt, make sure:

1. The requirements.txt files are properly formatted (no comments or Python code)
2. For Windows users:
   ```powershell
   # Install C2 server dependencies
   cd AttackBots\c2_server
   pip install flask==2.3.3 requests==2.31.0

   # Install exploit framework dependencies
   cd ..\exploit
   pip install requests urllib3 scapy paramiko cryptography psutil tqdm setuptools wheel python-nmap flask werkzeug colorama tabulate netifaces ifaddr
   ```
3. For Linux users:
   ```bash
   # Install C2 server dependencies
   cd AttackBots/c2_server
   pip3 install flask==2.3.3 requests==2.31.0

   # Install exploit framework dependencies
   cd ../exploit
   pip3 install requests urllib3 scapy paramiko cryptography psutil tqdm setuptools wheel python-nmap flask werkzeug colorama tabulate netifaces ifaddr
   ```

#### Troubleshooting C2 Server Web Interface

If you encounter an "Error loading dashboard: dashboard.html" when accessing the C2 server web interface, you need to create the Flask templates directory and files:

1. Create the templates directory:
   ```powershell
   # For Windows
   mkdir AttackBots\c2_server\templates
   
   # For Linux
   mkdir -p AttackBots/c2_server/templates
   ```

2. Create the required HTML template files:
   - dashboard.html
   - bots.html
   - credentials.html
   - scans.html
   - ddos.html
   
   These template files should be placed in the templates directory to enable the Flask web interface to function correctly. The repository includes these files in the correct location.

## Usage Guide

### 1. GNS3 Network Setup

1. Launch GNS3
2. Create a new project
3. Add the following devices:
   - Cisco 7200 router for network routing
   - Ubuntu Server for MQTT broker
   - Multiple IoT device nodes (can be Docker containers)
   - Kali Linux node for attack simulation

### 2. MQTT Communication Setup

1. Configure the MQTT broker on the Ubuntu Server node:
   ```bash
   python mqttbroker.py --host 0.0.0.0 --port 1883
   ```

2. Set up publisher clients on IoT device nodes:
   ```bash
   python publish.py --broker <broker_ip> --topic sensors/temperature --interval 5
   ```

### 3. Attack Simulation

1. Start the Command & Control server:
   ```bash
   cd AttackBots/c2_server
   python c2_server.py
   ```

2. Launch the exploit framework:
   ```bash
   cd AttackBots/exploit
   python launcher.py --target 192.168.1.0/24 --threads 10
   ```

3. Access the web interface at `http://<c2_server_ip>:5000` to monitor and control the attack simulation

### 4. Analysis and Monitoring

1. Use Wireshark to capture and analyze network traffic
2. Monitor MQTT message flow to detect anomalies
3. Track system logs on IoT devices for signs of compromise

## Security Considerations

⚠️ **WARNING**: This system is designed for educational and research purposes only. Use it responsibly and only on systems you own or have explicit permission to test.

- Always operate this testbed in an isolated network environment
- Never connect the testbed to production networks or the internet
- Use strong, unique passwords for all components
- Follow legal and ethical guidelines when conducting security research

## Troubleshooting

### Common Issues

1. **MQTT Connection Failures**:
   - Verify IP addressing and network connectivity
   - Check that the MQTT broker is running and accessible
   - Ensure port 1883 is open on all relevant devices

2. **GNS3 Performance Issues**:
   - Reduce the number of concurrent devices
   - Allocate more resources to GNS3
   - Use lightweight container images when possible

3. **Attack Simulation Errors**:
   - Check dependencies installation
   - Verify network connectivity between attack nodes and targets
   - Review C2 server logs for error messages

## Usage

For detailed instructions on how to use the IoT Digital Twin Security Testbed, please refer to the [USAGE.md](USAGE.md) file, which includes:

- How to start the C2 server
- How to register attack bots
- How to launch DDoS attacks
- How to use the demo environment
- Security warnings and best practices

## References

- MQTT Broker Setup
- GNS3 Documentation: [https://docs.gns3.com/](https://docs.gns3.com/)
- IoT Security Best Practices
