# IoT Digital Twin Security Testbed

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)](https://github.com)

## ⚠️ **IMPORTANT DISCLAIMER**

This project is designed for **educational and research purposes only**. It is intended for use in isolated laboratory environments to help security researchers, students, and professionals understand IoT vulnerabilities and develop defensive strategies.

**DO NOT USE ON PRODUCTION SYSTEMS OR NETWORKS YOU DO NOT OWN**

## 📋 Overview

This repository provides a comprehensive IoT digital twin environment for security testing and vulnerability research. The project enables researchers and security professionals to simulate IoT networks, deploy attack vectors, and analyze vulnerabilities in a controlled environment.

### Key Features

- **IoT Device Simulation**: MQTT-based communication system for simulating IoT devices
- **Attack Simulation Framework**: Comprehensive threat simulation tools
- **Network Vulnerability Assessment**: Automated scanning and exploitation tools
- **Command & Control Infrastructure**: Simulated botnet management capabilities
- **Educational Research Tools**: Comprehensive logging and analysis features

## 🏗️ Project Structure

```
iot-digital-twin/
├── Agent/                     # IoT Device Agents & Communication
│   ├── mqttbroker.py         # MQTT broker implementation
│   └── publish.py            # MQTT publishing utilities
├── AttackThreat/             # Attack Simulation Framework
│   ├── main.py               # Main attack simulation controller
│   ├── requirements.txt      # Python dependencies
│   ├── research_db.sqlite    # Attack research database
│   ├── setup.py              # Package setup configuration
│   ├── QUICKSTART.md         # Quick start guide
│   ├── README.md             # Attack framework documentation
│   ├── bot_templates/        # Bot deployment templates
│   │   └── bot_client.sh     # Bot client script
│   └── modules/              # Core attack modules
│       ├── __init__.py       # Module initialization
│       ├── bruteforce.py     # Brute force attack implementation
│       ├── database.py       # Database management
│       ├── ddos_control.py   # DDoS attack coordination
│       ├── infection.py      # Bot deployment and infection
│       ├── scanner.py        # Network scanning utilities
│       └── utils.py          # Common utilities and helpers
├── README.md                 # This file
└── .gitignore               # Git ignore configuration
```

## 🚀 Quick Start

### Prerequisites

- **Operating System**: Windows 10/11 or Ubuntu 20.04+
- **Python**: Version 3.8 or higher
- **Network**: Isolated lab environment recommended
- **Dependencies**: See requirements.txt files in each component

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/iot-digital-twin.git
   cd iot-digital-twin
   ```

2. **Set up Python environment**:
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   # On Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   # Install AttackThreat framework dependencies
   cd AttackThreat
   pip install -r requirements.txt
   cd ..
   
   # Install MQTT agent dependencies
   cd Agent
   pip install paho-mqtt
   cd ..
   ```

### Basic Usage

#### 1. Start MQTT Broker (IoT Communication)

```bash
cd Agent
python mqttbroker.py
```

#### 2. Run Attack Simulation Framework

```bash
cd AttackThreat
python main.py
```

The attack simulation framework provides an interactive menu with the following options:
- 🔍 Network Discovery Scan
- 🔓 Brute Force Attack
- 🦠 Deploy Bot Infection
- 🚀 Start DDoS Attack
- ⏹️ Stop DDoS Attack
- 📊 Show Attack Status
- 📋 View Database Logs
- 🧹 Clear Database

#### 3. Sample Attack Workflow

1. **Network Discovery**: Scan for vulnerable IoT devices
2. **Credential Testing**: Attempt brute force attacks using common IoT passwords
3. **Device Compromise**: Deploy bot agents to compromised devices
4. **Attack Coordination**: Execute coordinated attacks (DDoS, data exfiltration)
5. **Analysis**: Review attack logs and success metrics

## 🔧 Configuration

### MQTT Broker Configuration

Edit the MQTT broker settings in `Agent/mqttbroker.py`:

```python
host = '10.10.10.10'          # MQTT broker host
port = 1883                   # MQTT broker port
username = 'your_username'    # MQTT username
password = 'your_password'    # MQTT password
topic = 'iot/devices/+'       # MQTT topic pattern
```

### Attack Framework Configuration

The attack framework uses a SQLite database (`research_db.sqlite`) to store:
- Discovered network targets
- Successful credential combinations
- Bot deployment status
- Attack execution logs

## 📚 Documentation

- **Quick Start Guide**: See `AttackThreat/QUICKSTART.md` for detailed setup instructions
- **Attack Framework**: See `AttackThreat/README.md` for comprehensive documentation
- **Module Documentation**: Each module in `AttackThreat/modules/` contains inline documentation

## 🛡️ Security Considerations

### Ethical Use Guidelines

- **Educational Purpose Only**: This tool is designed for learning and research
- **Authorized Testing**: Only use on systems you own or have explicit permission to test
- **Isolated Environments**: Always run in isolated lab networks, never on production systems
- **Legal Compliance**: Ensure compliance with local laws and regulations
- **Responsible Disclosure**: Report discovered vulnerabilities through proper channels

### Safety Measures

- Use virtual machines for testing
- Implement network segmentation
- Monitor resource usage during testing
- Maintain proper logging for audit purposes
- Implement cleanup procedures after testing

## 🤝 Contributing

Contributions are welcome for educational improvements and bug fixes. Please ensure all contributions maintain the educational focus and ethical guidelines of the project.

### Development Guidelines

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add educational feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Legal Notice

**IMPORTANT**: The authors and contributors are not responsible for any misuse of this software. Users are solely responsible for ensuring compliance with applicable laws and regulations. This software is provided "as is" without warranty of any kind.

## 🆘 Support

For questions related to educational use:

1. Check the documentation and quick start guides
2. Review the troubleshooting sections
3. Submit issues through the project repository
4. Consult the inline code documentation

## 🙏 Acknowledgments

This project incorporates various cybersecurity research concepts and techniques for educational purposes. It is designed to help security researchers understand IoT vulnerabilities and develop effective defensive strategies.

---

**Remember**: Always use this tool responsibly and only in authorized environments. The goal is to improve IoT security through education and research, not to cause harm.
