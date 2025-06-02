# Mirai-Inspired Attack Bot System
## Educational/Research Purpose Only

⚠️ **WARNING**: This system is designed for educational and research purposes only. Unauthorized access to computer systems is illegal and unethical. Use this tool responsibly and only on systems you own or have explicit permission to test.

## Overview

This is a comprehensive implementation of a Mirai-inspired botnet system designed for educational purposes and cybersecurity research. The system demonstrates various attack techniques, persistence mechanisms, and evasion strategies commonly used by IoT botnets.

## System Architecture

```
AttackBots/
├── c2_server/              # Command & Control Server
│   ├── c2_server.py       # Main C2 server
│   ├── communication.py   # Bot communication handler
│   ├── database.py        # Bot database management
│   ├── ddos_coordinator.py # DDoS attack coordination
│   ├── web_ui.py          # Web-based management interface
│   └── requirements.txt   # C2 server dependencies
│
└── exploit/               # Attack Bot Components
    ├── exploit.py         # Main exploit controller
    ├── scanner.py         # Network scanning module
    ├── bruteforce.py      # Brute force attack module
    ├── c2_communication.py # C2 communication client
    ├── ddos_manager.py    # DDoS attack manager
    ├── device_manager.py  # Compromised device manager
    ├── session_manager.py # Session persistence
    ├── launcher.py        # System launcher
    └── requirements.txt   # Bot dependencies
```

## Features

### Core Attack Capabilities
- **Network Scanning**: Multi-threaded port scanning and service detection
- **Brute Force Attacks**: Telnet credential attacks using common IoT passwords
- **Device Fingerprinting**: Automatic device type and OS identification
- **Persistence Mechanisms**: Multiple methods for maintaining access
- **DDoS Attacks**: SYN flood, UDP flood, HTTP flood, and DNS amplification attacks
- **Competing Malware Removal**: Kills other botnet processes (Mirai-inspired)
- **Binary Payload Delivery**: Multiple methods to deliver architecture-specific malware
- **Credential Harvesting**: Collection and storage of compromised device credentials

### Command & Control
- **HTTP-based C2**: RESTful API for bot management
- **Real-time Communication**: Heartbeat and command distribution
- **Web Interface**: Browser-based botnet management
- **Database Integration**: SQLite-based bot tracking

### Evasion & Anti-Analysis
- **Sandbox Detection**: VM and analysis environment detection
- **Process Obfuscation**: Hide process names and behavior
- **Network Evasion**: Randomized timing and traffic patterns
- **Self-Destruction**: Cleanup mechanisms to remove traces

### Enhanced Mirai-like Features

This system incorporates several features inspired by the Mirai botnet:

1. **Process Killer**: Automatically identifies and terminates competing malware processes
2. **Default Credential Database**: Extensive collection of IoT default credentials
3. **Multi-Architecture Support**: Targets different CPU architectures (ARM, MIPS, x86)
4. **DNS Amplification Attacks**: Advanced DDoS technique used by Mirai
5. **Binary Payload Delivery**: Multiple methods to deliver malware to compromised devices
6. **Pure Python Attack Implementations**: Cross-platform attack capabilities
7. **Credential Harvesting**: Collection and storage of compromised credentials
8. **Advanced Evasion Techniques**: Methods to avoid detection and analysis

These features make this system valuable for educational purposes, helping security researchers understand how IoT botnets operate and develop effective defenses against them.

## Installation

### Prerequisites
- Python 3.7 or higher
- pip package manager
- Administrative privileges (for some features)

### Quick Setup
```bash
cd AttackBots/exploit
python launcher.py --check-deps
```

### Manual Installation
```bash
# Install bot dependencies
cd AttackBots/exploit
pip install -r requirements.txt

# Install C2 server dependencies
cd ../c2_server
pip install -r requirements.txt
```

## Usage

### Launcher Interface
The launcher provides an easy way to start and configure the system:

```bash
cd AttackBots/exploit
python launcher.py --mode interactive
```

### Available Modes
- **Interactive**: Manual control with command interface
- **Auto**: Automatic scanning and exploitation
- **C2-only**: Start only the C2 server
- **Config**: Interactive configuration setup
- **Status**: Show system status

### Configuration
Run the configuration wizard:
```bash
python launcher.py --mode config
```

### Starting the System

#### Full System (C2 + Bot)
```bash
python launcher.py --mode auto
```

#### Interactive Mode
```bash
python launcher.py --mode interactive
```

#### C2 Server Only
```bash
python launcher.py --mode c2-only
```

### Manual Operation

#### Start C2 Server
```bash
cd c2_server
python c2_server.py --host 0.0.0.0 --port 8080
```

#### Start Attack Bot
```bash
cd exploit
python exploit.py --c2-host 127.0.0.1 --c2-port 8080 --mode interactive
```

## Command Reference

### Launcher Commands
```bash
python launcher.py [OPTIONS]

Options:
  --mode {auto,interactive,c2-only,config,status}
  --check-deps          Check and install dependencies
  --no-c2              Don't start C2 server
```

### Exploit Controller Commands
```bash
python exploit.py [OPTIONS]

Options:
  --c2-host HOST       C2 server hostname
  --c2-port PORT       C2 server port
  --mode {auto,interactive}
  --silent             Run in silent mode
  --no-persistence     Disable persistence mechanisms
  --no-evasion         Disable evasion techniques
```

### Interactive Mode Commands
When running in interactive mode, the following commands are available:

- `help` - Show available commands
- `status` - Show bot status
- `scan <target>` - Scan and exploit target range
- `devices` - Show compromised devices
- `ddos <target>` - Start DDoS attack on target
- `stats` - Show attack statistics
- `quit/exit` - Exit interactive mode

## Technical Details

### Network Scanning
The scanner module implements:
- Multi-threaded TCP port scanning
- Service detection and banner grabbing
- CIDR range support
- Configurable timeouts and thread pools

### Brute Force Attacks
The brute force module includes:
- Telnet-specific attack implementations
- Common IoT device credentials database
- Randomized timing to avoid detection
- Success rate tracking

### Device Management
Device management features:
- Automatic device categorization
- Health monitoring and status tracking
- Command execution on compromised devices
- Session persistence across reboots

### DDoS Capabilities
DDoS attack types supported:
- **SYN Flood**: TCP SYN packet flooding
- **UDP Flood**: UDP packet flooding
- **HTTP Flood**: HTTP request flooding
- **Distributed Attacks**: Coordinated multi-bot attacks

### Persistence Mechanisms
Methods for maintaining access:
- Cron job installation
- Systemd service creation
- Hidden file execution
- Registry modification (Windows)

### Evasion Techniques
Anti-analysis features:
- Virtual machine detection
- Debugger detection
- Sandbox environment detection
- Process name obfuscation
- Network traffic randomization

## Configuration Options

### Bot Configuration
```json
{
  "c2_host": "127.0.0.1",
  "c2_port": 8080,
  "scan_threads": 50,
  "scan_timeout": 5,
  "exploit_delay": [1, 3],
  "persistence_enabled": true,
  "evasion_enabled": true,
  "target_ranges": [
    "192.168.1.0/24",
    "192.168.0.0/24"
  ]
}
```

### C2 Server Configuration
- Database settings
- Authentication mechanisms
- API rate limiting
- Web interface customization

## Security Considerations

### Legal Compliance
- Only use on systems you own or have permission to test
- Comply with local laws and regulations
- Obtain proper authorization before testing

### Ethical Guidelines
- Use for educational purposes only
- Do not cause harm or disruption
- Report vulnerabilities responsibly
- Respect privacy and data protection

### Safety Measures
- Test in isolated environments
- Use virtual machines for testing
- Monitor resource usage
- Implement proper cleanup procedures

## Troubleshooting

### Common Issues

#### Dependencies Not Found
```bash
python launcher.py --check-deps
```

#### Connection Refused to C2
- Check firewall settings
- Verify C2 server is running
- Confirm network connectivity

#### Permission Denied
- Run with appropriate privileges
- Check file permissions
- Verify network access rights

### Debug Mode
Enable verbose logging:
```bash
python exploit.py --mode interactive --debug
```

### Log Files
System logs are stored in:
- `/tmp/attackbot_<bot_id>.log` (Linux)
- `%TEMP%\attackbot_<bot_id>.log` (Windows)

## Research Applications

### Cybersecurity Education
- Understanding botnet operations
- IoT security vulnerability assessment
- Network defense strategy development

### Penetration Testing
- IoT device security testing
- Network segmentation validation
- Incident response training

### Academic Research
- Malware behavior analysis
- Network security research
- IoT security assessment

## Disclaimer

This software is provided for educational and research purposes only. The authors and contributors are not responsible for any misuse of this software. Users are solely responsible for ensuring compliance with applicable laws and regulations.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome for educational improvements and bug fixes. Please ensure all contributions maintain the educational focus and ethical guidelines of the project.

## Support

For questions or issues related to educational use:
1. Check the troubleshooting section
2. Review the configuration options
3. Consult the technical documentation
4. Submit issues through the project repository

## Acknowledgments

This project is inspired by the Mirai botnet for educational purposes. It incorporates various cybersecurity concepts and techniques for learning and research applications.
