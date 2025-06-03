# IoT Lab Security Testing Framework

A Python-based educational framework for testing IoT device security in isolated lab environments. This tool is designed specifically for cybersecurity education and research in controlled GNS3 lab setups.

## 🎯 Purpose

This framework helps security researchers and students understand IoT vulnerabilities by:
- Discovering IoT devices with open Telnet services
- Testing common default credentials
- Documenting vulnerable devices for analysis
- Providing interactive access for security research

## ⚠️ Important Notice

**This tool is intended ONLY for use in isolated lab environments that you own and control.** Never use this tool against systems you do not have explicit permission to test. This framework is designed for educational purposes and ethical security research.

## 🏗️ Lab Setup

This framework is designed to work with GNS3 lab environments on Ubuntu containing:
- **IoT Devices**: IP cameras, sensors, smart home devices (simulated using lightweight VMs)
- **Network Infrastructure**: Routers, switches, access points
- **Security Tools**: Kali Linux for additional testing capabilities
- **Isolated Subnets**: Segregated networks for safe testing
- **MQTT Brokers**: Message queuing services for IoT communication

### Ubuntu-Specific Setup Requirements
- **KVM/QEMU**: Hardware virtualization support
- **Bridge Networking**: For GNS3 VM connectivity
- **Docker**: Container support for lightweight services
- **TightVNC**: Remote access to virtual machines

## 🚀 Installation

### Prerequisites
- **Operating System**: Ubuntu 22.04.4 LTS (recommended)
- **Python**: Python 3.8 or higher (typically pre-installed)
- **GNS3**: Lab environment setup with virtualization support
- **Network**: Isolated testing environment

### System Requirements
- KVM virtualization support enabled
- Minimum 4GB RAM (8GB recommended for multiple VMs)
- 20GB available disk space
- Network access for package installation

### Setup Instructions

1. **Update system packages:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Python development tools (if not present):**
   ```bash
   sudo apt install python3 python3-pip python3-venv python3-dev -y
   ```

3. **Clone the repository:**
   ```bash
   git clone https://github.com/Siong23/iot-digital-twin.git
   cd iot-digital-twin/AttackThreat
   ```

4. **Create a virtual environment:**
   ```bash
   python3 -m venv iot_lab_env
   ```

5. **Activate the virtual environment:**
   ```bash
   source iot_lab_env/bin/activate
   ```

6. **Install dependencies:**
   ```bash
   # Install all optional dependencies:
   pip install -r requirements.txt
   
   # Or install selectively for enhanced UI:
   pip install colorama tqdm
   
   # Or run with no dependencies (basic functionality):
   # No installation needed - uses Python standard library only
   ```

7. **Verify installation:**
   ```bash
   python3 exploit.py --help
   ```

## 📋 Usage

### Command Line Interface

#### 1. Scan a Subnet (Basic Usage)
```bash
# Scan for devices with open Telnet ports
python3 exploit.py --scan 192.168.1.0/24
python3 exploit.py --scan 10.10.10.0/24
python3 exploit.py --scan 11.10.10.0/24
```

#### 2. Use Custom Credentials File
```bash
python3 exploit.py --scan 192.168.1.0/24 --creds credentials.txt
```

#### 3. List Discovered Vulnerable Devices
```bash
python3 exploit.py --list
```

#### 4. Open Interactive Session
```bash
python3 exploit.py --session 192.168.1.100
```

### Interactive Mode

Run without arguments for menu-driven interface:
```bash
python3 exploit.py
```

Then select:
1. Scan subnet
2. List vulnerable devices
3. Open session

## 📁 File Structure

```
iot-lab-framework/
├── exploit.py      # Main framework script
├── credentials.txt        # Default credential pairs for testing
├── requirements.txt       # Optional Python dependencies
├── README.md             # This file
└── iot_lab_results.db    # SQLite database (created automatically)
```

## 🔧 Configuration

### Credentials File Format
The `credentials.txt` file should contain username:password pairs, one per line:
```
admin:admin
root:password
ipcamadmin:admin
temphumidadmin:admin
user:12345
```

### Database Storage
Results are automatically stored in `iot_lab_results.db` (SQLite database) containing:
- IP addresses
- Successful credentials
- Device banners
- Discovery timestamps

## 🎓 Educational Use Cases

### Lab Scenarios
1. **IoT Device Discovery**: Learn how attackers find vulnerable devices
2. **Credential Analysis**: Study common default passwords in IoT devices
3. **Network Segmentation**: Test isolation between network segments
4. **Incident Response**: Practice detecting and responding to compromises
5. **Vulnerability Assessment**: Document security weaknesses in lab devices

### Learning Objectives
- Understand IoT security fundamentals
- Practice ethical hacking methodologies
- Learn network reconnaissance techniques
- Develop incident response skills
- Study authentication vulnerabilities

## 🔍 Sample Output

```
[INFO] Scanning subnet 192.168.1.0/24 for open Telnet ports...
[+] Found open Telnet on 192.168.1.100
[+] Found open Telnet on 192.168.1.101
[INFO] Found 2 hosts with open Telnet ports
[INFO] Loaded 200 credential pairs
[INFO] Testing 192.168.1.100...
[+] SUCCESS: 192.168.1.100 - admin:admin
[INFO] Testing 192.168.1.101...
[+] SUCCESS: 192.168.1.101 - ipcamadmin:admin
```

## 🛡️ Security Considerations

### Lab Environment Only
- Use only in isolated, controlled environments
- Never test against production systems
- Ensure proper network isolation
- Document all testing activities

### Rate Limiting
The framework includes built-in rate limiting to prevent overwhelming devices and to simulate realistic attack patterns.

### Data Protection
- All results stored locally in SQLite database
- No data transmitted outside your lab
- Credentials stored in plain text (lab environment only)

## 🐛 Troubleshooting

### Common Issues

1. **"Connection refused" errors:**
   - Verify target devices are running and accessible
   - Check network connectivity in your GNS3 lab
   - Ensure Telnet service is enabled on target devices
   - Verify Ubuntu firewall settings: `sudo ufw status`

2. **"No vulnerable devices found":**
   - Verify credentials file format (Linux line endings)
   - Check if devices use non-standard login prompts
   - Increase timeout values for slow VMs
   - Ensure proper network bridging in GNS3

3. **Database errors:**
   - Check file permissions: `ls -la iot_lab_results.db`
   - Ensure write permissions: `chmod 644 iot_lab_results.db`
   - Verify available disk space: `df -h`
   - Install SQLite3 if missing: `sudo apt install sqlite3`

4. **Python/Virtual Environment Issues:**
   - Ensure Python 3.8+: `python3 --version`
   - Activate virtual environment: `source iot_lab_env/bin/activate`
   - Reinstall packages: `pip install --upgrade -r requirements.txt`

5. **GNS3 Connectivity Issues:**
   - Check bridge configuration: `ip addr show`
   - Verify KVM support: `sudo kvm-ok`
   - Restart GNS3 service: `sudo systemctl restart gns3-server`

### Debug Mode
Enable verbose logging for troubleshooting:
```bash
# Add debug output
python3 exploit.py --scan 192.168.1.0/24 --verbose

# Check system logs
sudo journalctl -f

# Monitor network traffic
sudo tcpdump -i any port 23
```

### Performance Optimization
For better performance on Ubuntu systems:
```bash
# Increase file descriptor limits
ulimit -n 4096

# Monitor system resources
htop
iotop
```

## 📚 Educational Resources

### Recommended Learning Path
1. **Set up Ubuntu-based GNS3 lab environment:**
   ```bash
   # Install GNS3 on Ubuntu
   sudo add-apt-repository ppa:gns3/ppa
   sudo apt update
   sudo apt install gns3-gui gns3-server
   ```

2. **Deploy various IoT device emulations in VMs**
3. **Configure network bridges and isolation**
4. **Run reconnaissance scans using this framework**
5. **Analyze discovered vulnerabilities and document findings**
6. **Practice remediation techniques in the lab environment**
7. **Implement network monitoring and detection rules**

### Ubuntu-Specific GNS3 Setup
```bash
# Add user to required groups
sudo usermod -aG libvirt $USER
sudo usermod -aG kvm $USER
sudo usermod -aG wireshark $USER

# Enable and start libvirt
sudo systemctl enable libvirtd
sudo systemctl start libvirtd

# Verify KVM acceleration
sudo kvm-ok
```

### Further Reading
- [IoT Security Best Practices for Ubuntu Labs](https://ubuntu.com/security/iot)
- [Network Penetration Testing Methodologies](https://www.offensive-security.com)
- [Ethical Hacking Guidelines and Legal Considerations](https://www.eccouncil.org)
- [GNS3 Ubuntu Installation and Setup Guide](https://docs.gns3.com/docs/getting-started/installation/linux)
- [KVM Virtualization on Ubuntu](https://ubuntu.com/server/docs/virtualization-kvm)
- [Ubuntu Server Security Hardening](https://ubuntu.com/security/hardening)

## 🤝 Contributing

This is an educational tool. Improvements and additional features are welcome:
- Enhanced device detection
- Additional credential databases
- Improved reporting features
- Better error handling
- Additional IoT protocols support

## 📄 License

This educational framework is provided for learning purposes. Use responsibly and ethically in controlled environments only.

## ⚖️ Legal Disclaimer

This tool is provided for educational and research purposes only. Users are responsible for complying with all applicable laws and regulations. Only use this tool in environments you own or have explicit permission to test. The authors are not responsible for any misuse of this tool.

---

**Remember**: Always practice ethical hacking and responsible disclosure. This tool is designed to help you learn about IoT security in a safe, controlled environment.