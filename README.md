# IoT Digital Twin Security Research Platform

A comprehensive security research platform for testing IoT network vulnerabilities in controlled lab environments using GNS3 simulation and automated attack frameworks.

## 🎯 Overview

This project provides a complete digital twin environment for IoT security research, combining:
- **Network Simulation**: GNS3-based IoT network topology
- **Attack Framework**: Automated exploitation and C2 infrastructure
- **Monitoring Platform**: Real-time web interface for attack coordination

## 🚨 Important Legal Notice

**This software is designed exclusively for educational and research purposes in controlled lab environments. It must never be used against systems without explicit written authorization. Users are fully responsible for complying with all applicable laws and regulations.**

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 22.04.4 LTS (recommended) or Windows 10/11
- **Hardware**: KVM support, minimum 8GB RAM, 50GB storage
- **Python**: 3.9 or later with pip and venv

### Essential Dependencies
- [KVM Support](https://www.cyberciti.biz/faq/linux-xen-vmware-kvm-intel-vt-amd-v-support/) (for virtualization)
- [make](https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/)
- [wget](https://www.cyberciti.biz/faq/how-to-install-wget-togetrid-of-error-bash-wget-command-not-found/)
- [konsole](https://www.ubuntumint.com/konsole-terminal-emulator/) (Linux terminal)
- [Docker](https://docs.docker.com/engine/install/)

### GNS3 Environment
- [GNS3](https://www.gns3.com/) simulation platform
- [Cisco 7200 router image](https://www.gns3.com/marketplace/appliances/cisco-7200)
- [Ubuntu Server](https://releases.ubuntu.com/22.04/) VMs
- [Kali Linux for GNS3](https://gns3.com/marketplace/appliances/kali-linux-2)
- Open vSwitch (fixed version)
- Ubuntu Guest Additions
- TightVNC for remote access

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/yourusername/iot-digital-twin.git
cd iot-digital-twin
```

### 2. Attack Framework Setup

#### For Windows Users:
```powershell
cd Scripts\AttackThreat
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### For Linux Users:
```bash
cd Scripts/AttackThreat
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start the C2 Server
```bash
cd Scripts/AttackThreat/c2_server
python run_c2.py
```

The web interface will be available at: `http://127.0.0.1:5000`

### 4. Run Network Exploitation
```bash
cd Scripts/AttackThreat
python exploit.py [C2_SERVER_IP] [TARGET_SUBNET]
```

Example:
```bash
python exploit.py 127.0.0.1 192.168.1.0/24
```

## 📁 Project Structure

```
iot-digital-twin/
├── README.md                 # Project documentation
├── Scripts/
│   ├── Agent/               # MQTT broker and agents
│   │   ├── mqttbroker.py   # MQTT message broker
│   │   └── publish.py      # Message publisher
│   └── AttackThreat/        # Main attack framework
│       ├── exploit.py       # Network exploitation tool
│       ├── bot_client.py    # IoT bot simulation
│       ├── credentials.py   # Credential management
│       ├── requirements.txt # Python dependencies
│       ├── README.md        # Framework documentation
│       └── c2_server/       # Command & Control server
│           ├── c2_server.py    # Main C2 server
│           ├── web_ui.py       # Web dashboard
│           ├── db_manager.py   # Database operations
│           ├── tn_manager.py   # Telnet manager
│           ├── run_c2.py       # Server launcher
│           └── requirements.txt # C2 dependencies
```

## 🔧 Features

### Attack Framework
- **Network Discovery**: Automated IoT device scanning
- **Credential Brute-forcing**: Telnet authentication bypass
- **Botnet Simulation**: Compromised device management
- **DDoS Coordination**: Distributed attack orchestration

### C2 Dashboard
- **Real-time Monitoring**: Live device status tracking
- **Attack Management**: Start/stop attacks remotely
- **Device Analytics**: Compromise statistics and metrics
- **Web Interface**: Modern, responsive control panel

### MQTT Integration
- **Broker Setup**: Secure MQTT communication
- **Device Simulation**: IoT device behavior modeling
- **Message Handling**: Command and data exchange

## 🛡️ Security Research Applications

- IoT vulnerability assessment
- Network defense testing
- Attack pattern analysis
- Security control validation
- Incident response training

## 📚 Documentation

- [Attack Framework Guide](Scripts/AttackThreat/README.md)
- [C2 Server Documentation](Scripts/AttackThreat/c2_server/README.md)
- [MQTT Broker Setup Guide](https://medium.com/gravio-edge-iot-platform/how-to-set-up-a-mosquitto-mqtt-broker-securely-using-client-certificates-82b2aaaef9c8)

## 🤝 Contributing

This is an educational research project. Contributions should focus on:
- Educational value enhancement
- Security research methodology
- Code quality and documentation
- Ethical use guidelines

## ⚖️ Legal Disclaimer

This software is provided for educational and research purposes only. The authors and contributors are not responsible for any misuse or damage caused by this software. Users must ensure compliance with all applicable laws and obtain proper authorization before testing on any systems.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 References

- [IoT Security Research Best Practices](https://www.nist.gov/cybersecurity)
- [Ethical Hacking Guidelines](https://www.ec-council.org/ethical-hacking/)
- [GNS3 Network Simulation](https://www.gns3.com/)
