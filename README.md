# IoT Digital Twin Security Testbed

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

> **⚠️ EDUCATIONAL USE ONLY**: This project is designed for educational purposes and authorized security research. Users are responsible for complying with all applicable laws and regulations.

## Overview

The IoT Digital Twin Security Testbed is a comprehensive framework designed to simulate, analyze, and test IoT security scenarios in a controlled environment. This project provides tools for understanding IoT vulnerabilities, attack vectors, and defense mechanisms through hands-on experimentation.

## 🚨 Important Disclaimers

- **Educational Purpose Only**: This framework is intended for learning and authorized research
- **Legal Compliance**: Users must ensure compliance with all local, state, and federal laws
- **Authorized Testing**: Only use on systems you own or have explicit permission to test
- **No Malicious Use**: Any malicious use of these tools is strictly prohibited
- **User Responsibility**: Users assume full responsibility for their actions

## Project Structure

```
iot-digital-twin/
├── Agent/                      # MQTT agent implementations
│   ├── mqtt_agent.py          # Main MQTT agent
│   └── config/                # Agent configurations
├── AttackBots/                 # Bot deployment and management
│   ├── bot_deployment.py      # Bot deployment scripts
│   ├── bot_manager.py         # Bot management system
│   └── README.md              # Bot documentation
├── AttackThreat/              # Main attack simulation framework
│   ├── main.py                # Framework entry point
│   ├── modules/               # Attack modules
│   ├── research_db.sqlite     # Research database
│   ├── requirements.txt       # Python dependencies
│   ├── installation.sh        # Ubuntu installation script
│   └── QUICKSTART.md          # Quick start guide
├── docs/                      # Documentation
└── README.md                  # This file
```

## Quick Start

### Prerequisites

- **Operating System**: Ubuntu 18.04+ or Windows 10+
- **Python**: 3.8 or higher
- **Network Access**: For MQTT broker communication
- **Permissions**: Administrative privileges for network tool installation

### Ubuntu Installation (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/iot-digital-twin.git
   cd iot-digital-twin/AttackThreat
   ```

2. **Run the installation script**:
   ```bash
   chmod +x installation.sh
   ./installation.sh
   ```

3. **Activate the virtual environment**:
   ```bash
   source venv/bin/activate
   ```

4. **Verify installation**:
   ```bash
   python main.py --help
   ```

### Manual Installation

If you prefer manual installation or the script doesn't work:

1. **Install system dependencies**:
   ```bash
   sudo apt update
   sudo apt install -y build-essential python3-dev python3-pip python3-venv
   sudo apt install -y nmap netcat-openbsd telnet openssh-client
   sudo apt install -y libffi-dev libssl-dev mosquitto-clients
   ```

2. **Set up Python environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```

## Configuration

### MQTT Broker Setup

The framework requires an MQTT broker for IoT device simulation:

1. **Install local MQTT broker**:
   ```bash
   sudo apt install mosquitto mosquitto-clients
   sudo systemctl start mosquitto
   sudo systemctl enable mosquitto
   ```

2. **Configure broker settings** in `Agent/config/mqtt_config.json`:
   ```json
   {
     "broker_host": "localhost",
     "broker_port": 1883,
     "username": null,
     "password": null,
     "topics": ["iot/sensors", "iot/commands"]
   }
   ```

### Attack Framework Configuration

Review and modify settings in `AttackThreat/config/` directory:

- **Network settings**: Target ranges and excluded IPs
- **Attack parameters**: Timing, intensity, and methods
- **Logging configuration**: Output formats and destinations

## Usage Examples

### Basic Network Reconnaissance

```bash
# Activate virtual environment
source venv/bin/activate

# Run basic network scan
python main.py --scan --target 192.168.1.0/24

# MQTT vulnerability assessment
python main.py --mqtt --broker localhost --port 1883
```

### IoT Device Simulation

```bash
# Start MQTT agents
cd Agent/
python mqtt_agent.py --config config/default.json

# Deploy attack bots
cd ../AttackBots/
python bot_deployment.py --count 5 --target-network 192.168.1.0/24
```

## Security Considerations

### Ethical Guidelines

1. **Authorization Required**: Never test systems without explicit permission
2. **Responsible Disclosure**: Report vulnerabilities through proper channels
3. **Educational Focus**: Use for learning and improving security posture
4. **Legal Compliance**: Understand and follow all applicable laws

### Safety Measures

1. **Isolated Environment**: Use dedicated test networks when possible
2. **Limited Scope**: Restrict testing to authorized systems only
3. **Monitoring**: Log all activities for audit purposes
4. **Cleanup**: Remove any test artifacts after completion

## Documentation

- **[Quick Start Guide](AttackThreat/QUICKSTART.md)**: Rapid deployment instructions
- **[Attack Bot Documentation](AttackBots/README.md)**: Bot deployment and management
- **[API Documentation](docs/api.md)**: Framework API reference
- **[Configuration Guide](docs/configuration.md)**: Detailed configuration options

## Contributing

We welcome contributions from the security research community:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature-name`
3. **Follow coding standards**: Use consistent formatting and documentation
4. **Test thoroughly**: Ensure all changes work in isolated environments
5. **Submit pull request**: Include detailed description of changes

### Contribution Guidelines

- All contributions must maintain the educational focus
- No malicious code or exploits
- Proper documentation required for new features
- Security-focused code reviews mandatory

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure proper user permissions for network tools
2. **Package Conflicts**: Use virtual environments to isolate dependencies
3. **Network Access**: Verify MQTT broker connectivity and firewall settings
4. **Python Version**: Ensure Python 3.8+ is installed and active

### Getting Help

- **Check logs**: Review application logs for error details
- **Verify configuration**: Ensure all config files are properly formatted
- **Test connectivity**: Verify network access to target systems
- **Update dependencies**: Keep all packages up to date

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Legal Notice

**IMPORTANT**: This software is provided for educational and research purposes only. The authors and contributors are not responsible for any misuse or damage caused by this software. Users must ensure they have proper authorization before testing any systems and must comply with all applicable laws and regulations.

By using this software, you acknowledge that you understand these terms and agree to use the tools responsibly and legally.

## Acknowledgments

- Security research community for methodologies and best practices
- Open source projects that make this framework possible
- Educational institutions promoting ethical security research

---

**Remember**: With great power comes great responsibility. Use these tools to make the digital world more secure, not less.