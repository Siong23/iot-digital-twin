# IoT Digital Twin Security Testbed

[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://python.org)
[![GNS3](https://img.shields.io/badge/GNS3-Compatible-green.svg)](https://gns3.com)
[![License](https://img.shields.io/badge/License-Educational-yellow.svg)](#license)

A comprehensive security testbed for IoT networks using GNS3 virtualization platform. This project provides a controlled environment for researching IoT vulnerabilities, testing security mechanisms, and understanding digital twin concepts in cybersecurity education.

## 🎯 Overview

This testbed simulates real-world IoT environments with digital twin capabilities, allowing security researchers and students to:

- **Study IoT Vulnerabilities**: Test common IoT device security flaws in a safe environment
- **Analyze Network Traffic**: Monitor MQTT and other IoT protocol communications
- **Security Assessment**: Perform penetration testing on virtualized IoT devices
- **Educational Research**: Learn about IoT security without risk to production systems

## 🏗️ Architecture

The testbed consists of several key components:

```
├── Agent/                 # MQTT broker and IoT simulation tools
│   ├── mqttbroker.py     # MQTT broker management
│   └── publish.py        # MQTT message publishing utilities
├── AttackThreat/         # Security testing framework
│   ├── exploit.py        # Automated vulnerability scanning
│   ├── exploit_interactive.py  # Interactive security testing
│   ├── credentials.txt   # Common IoT default credentials
│   └── requirements.txt  # Python dependencies
└── README.md            # This documentation
```

## 🚀 Quick Start

### Prerequisites

**Operating System**: Ubuntu 22.04.4 LTS (recommended)

**Required Dependencies**:
- KVM virtualization support
- GNS3 network simulator
- Python 3.x with python3-venv
- Docker
- Standard Linux utilities (make, wget, konsole)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Siong23/iot-digital-twin.git
   cd iot-digital-twin
   ```

2. **Install Python dependencies**:
   ```bash
   cd AttackThreat
   pip install -r requirements.txt
   ```

3. **Set up GNS3 environment** with the required appliances (see [Dependencies](https://github.com/Siong23/iot-digital-twin/tree/main?tab=readme-ov-file#-dependencies))

### Basic Usage

1. **Start the MQTT broker**:
   ```bash
   cd Agent
   python3 mqttbroker.py
   ```

2. **Run security assessments**:
   ```bash
   cd AttackThreat
   python3 exploit.py  # Automated scanning
   # or
   python3 exploit_interactive.py  # Interactive mode
   ```

## 📋 Dependencies

### GNS3 Appliances
- [Cisco 7200 Router](https://www.gns3.com/marketplace/appliances/cisco-7200) - Network routing simulation
- [Kali Linux](https://gns3.com/marketplace/appliances/kali-linux-2) - Security testing platform
- [Fixed Open vSwitch](https://gitlab.com/Fumeaux/openvswitch) - Virtual switching
- Ubuntu Server - IoT device simulation
- Ubuntu Guest Additions - Enhanced VM functionality
- TightVNC - Remote access capabilities

### System Requirements
- **Virtualization**: KVM support enabled
- **RAM**: Minimum 8GB (16GB recommended)
- **Storage**: 50GB+ available space
- **Network**: Internet connection for appliance downloads

## 🔧 Configuration

### MQTT Broker Setup
Configure secure MQTT communication using client certificates. Follow the [detailed MQTT setup guide](https://medium.com/gravio-edge-iot-platform/how-to-set-up-a-mosquitto-mqtt-broker-securely-using-client-certificates-82b2aaaef9c8).

### Network Topology
Design your GNS3 topology to include:
- IoT devices (simulated using lightweight VMs)
- Network infrastructure (routers, switches)
- Security monitoring tools (Kali Linux)
- MQTT broker services

## ⚠️ Security Notice

**⚠️ IMPORTANT**: This testbed is designed exclusively for educational and research purposes in controlled environments. Only use these tools on systems you own or have explicit permission to test. Unauthorized use of security testing tools is illegal and unethical.

## 🎓 Educational Use Cases

- **Cybersecurity Courses**: Hands-on IoT security training
- **Research Projects**: IoT vulnerability analysis
- **Security Workshops**: Practical penetration testing
- **Digital Twin Concepts**: Understanding IoT system modeling

## 📚 Documentation

For detailed setup instructions and advanced usage, refer to:
- [AttackThreat Framework Documentation](./AttackThreat/README.md)
- [MQTT Security Configuration Guide](https://medium.com/gravio-edge-iot-platform/how-to-set-up-a-mosquitto-mqtt-broker-securely-using-client-certificates-82b2aaaef9c8)

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests for improvements.

## 📄 License

This project is intended for educational and research purposes. Please ensure compliance with your institution's policies and applicable laws when using this testbed.

## 📧 Contact

For questions or collaboration opportunities, please open an issue or contact the repository maintainer.

---

**Repository**: https://github.com/Siong23/iot-digital-twin