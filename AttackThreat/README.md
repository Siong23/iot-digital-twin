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

This framework is designed to work with GNS3 lab environments containing:
- IoT devices (IP cameras, sensors, etc.)
- Network infrastructure (routers, switches)
- Isolated subnets for safe testing

## 🚀 Installation

### Prerequisites
- Python 3.6 or higher
- GNS3 lab environment (recommended)
- Isolated network for testing

### Setup Instructions

1. **Clone or download the framework files:**
   ```bash
   # Download the main files:
   # - exploit.py
   # - credentials.txt
   # - requirements.txt
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv iot_lab_env
   ```

3. **Activate the virtual environment:**
   ```bash
   # On Linux/macOS:
   source iot_lab_env/bin/activate
   
   # On Windows:
   iot_lab_env\Scripts\activate
   ```

4. **Install dependencies:**
   ```bash
   # Install all optional dependencies:
   pip install -r requirements.txt
   
   # Or install selectively for better UI:
   pip install colorama tqdm
   
   # Or run with no dependencies (basic functionality):
   # No installation needed - uses Python standard library only
   ```

## 📋 Usage

### Command Line Interface

#### 1. Scan a Subnet
```bash
# Scan for devices with open Telnet ports
python exploit.py --scan 192.168.1.0/24
python exploit.py --scan 10.10.10.0/24
python exploit.py --scan 11.10.10.0/24
```

#### 2. Use Custom Credentials File
```bash
python exploit.py --scan 192.168.1.0/24 --creds credentials.txt
```

#### 3. List Discovered Vulnerable Devices
```bash
python exploit.py --list
```

#### 4. Open Interactive Session
```bash
python exploit.py --session 192.168.1.100
```

### Interactive Mode

Run without arguments for menu-driven interface:
```bash
python exploit.py
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
   - Check network connectivity in your lab
   - Ensure Telnet service is enabled on target devices

2. **"No vulnerable devices found":**
   - Verify credentials file format
   - Check if devices use non-standard login prompts
   - Increase timeout values for slow devices

3. **Database errors:**
   - Ensure write permissions in the current directory
   - Check available disk space
   - Verify SQLite3 is available

### Debug Mode
Add verbose output by modifying the script or using print statements to track execution.

## 📚 Educational Resources

### Recommended Learning Path
1. Set up isolated GNS3 lab environment
2. Deploy various IoT device emulations
3. Run reconnaissance scans
4. Analyze discovered vulnerabilities
5. Practice remediation techniques
6. Document findings and lessons learned

### Further Reading
- IoT Security Best Practices
- Network Penetration Testing Methodologies
- Ethical Hacking Guidelines
- GNS3 Lab Setup Tutorials

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