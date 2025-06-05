# IoT Lab Security Testing Framework

A Python-based educational framework for testing IoT device security in isolated lab environments. This tool is designed specifically for cybersecurity education and research in controlled lab setups.

## 🎯 Purpose

This framework helps security researchers and students understand IoT vulnerabilities by:
- Discovering IoT devices with open Telnet services
- Testing common default credentials
- Documenting vulnerable devices for analysis
- Providing interactive access for security research
- Demonstrating coordinated attack techniques in a controlled environment

## ⚠️ Important Notice

**This tool is intended ONLY for use in isolated lab environments that you own and control.** Never use this tool against systems you do not have explicit permission to test. This framework is designed for educational purposes and ethical security research.

## 🚀 Installation

### Prerequisites
- **Python**: Python 3.8 or higher
- **Network**: Isolated testing environment

### System Requirements
- Minimum 4GB RAM (8GB recommended for multiple devices)
- 20GB available disk space
- Network access for package installation

### Setup Instructions

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/Siong23/iot-digital-twin.git
   cd iot-digital-twin/AttackThreat
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```powershell
   python exploit_interactive.py --help
   ```

## 📋 Usage

### Enhanced Interactive Mode

The interactive version (`exploit_interactive.py`) provides a user-friendly menu-driven interface with improved error handling and user experience:

```powershell
python exploit_interactive.py
```

**Available Operations:**
1. **Scan subnet for vulnerable devices** - Discover IoT devices with open Telnet ports
2. **List discovered vulnerable devices** - View all identified vulnerable devices
3. **Show discovered credentials** - Display recovered credentials in a clean format
4. **Connect to vulnerable device** - Access a specific device with interactive commands
5. **Run coordinated reconnaissance** - Execute parallel recon across all compromised devices
6. **Launch distributed DDoS attack** - Coordinate attacks from all compromised devices
7. **Change scan speed** - Adjust scanning parameters for different environments
8. **Exit** - Quit the application

### Key Features

#### Improved User Experience
- **Continuous menu display** - Menu redisplays after each operation
- **Error handling** - Invalid inputs are gracefully handled without crashing
- **Interactive prompts** - Clear instructions at each step
- **Confirmation before destructive actions** - Safety measures for attack functions
- **Progress indicators** - Visual feedback during long operations

#### Scanning Capabilities
- **Multiple scan speeds** - Choose from slow/stealthy to turbo mode
- **Custom credential files** - Use your own credential list or default
- **Subnet scanning** - Scan entire network ranges for vulnerable devices
- **Automated brute forcing** - Test common credentials against discovered devices

#### Individual Device Interaction
When connecting to a compromised device (Option 4):
- **Command execution** - Run arbitrary commands on the compromised device
- **Interactive shell** - Full shell access with `exit_shell` command to return
- **Automated reconnaissance** - Run predefined recon commands
- **Exploitation commands** - Execute common exploitation techniques
- **Password handling** - Automatic password entry for sudo commands

#### Coordinated Operations
- **Distributed DDoS Attack (Option 6)**:
  - Launch attacks from all compromised devices simultaneously
  - Central command and control interface
  - Automatic password handling across all devices
  - Coordinated attack termination with one keystroke

- **Coordinated Reconnaissance (Option 5)**:
  - Gather intelligence from multiple compromised devices in parallel
  - Collate system information from across the network
  - Map the environment from multiple vantage points

#### Speed Configuration
Four speed modes available (Option 7):
- **Slow** - 10 threads, 2s delay (stealthy)
- **Normal** - 50 threads, 0.5s delay (balanced)
- **Fast** - 100 threads, 0.1s delay (aggressive)
- **Turbo** - 200 threads, no delay (maximum speed - use with caution!)

### Command Line Options

For headless or scripted operation, command-line arguments are supported:

```powershell
# Scan a subnet with default settings
python exploit_interactive.py --scan 192.168.1.0/24

# Use custom credentials file
python exploit_interactive.py --scan 192.168.1.0/24 --creds mycreds.txt

# Use faster scanning speed
python exploit_interactive.py --scan 192.168.1.0/24 --speed fast

# List discovered devices
python exploit_interactive.py --list

# Show only credentials
python exploit_interactive.py --creds-only

# Connect to specific device
python exploit_interactive.py --session 192.168.1.100
```

## 📁 File Structure

```
AttackThreat/
├── exploit_interactive.py        # Enhanced interactive version
├── exploit_interactive_backup.py # Backup of interactive version
├── exploit.py                    # Basic framework script
├── credentials.txt               # Default credential pairs for testing
├── requirements.txt              # Python dependencies
├── README.md                     # This documentation
├── cameradarexploit.sh           # Camera exploitation helper script
└── iot_lab_results.db            # SQLite database (created automatically)
```

## 🔧 Configuration

### Credentials File Format
The `credentials.txt` file contains username:password pairs, one per line:
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
6. **Botnet Simulation**: Understand how attackers leverage multiple compromised devices
7. **Distributed Attack Analysis**: Study the impact of coordinated attacks

## 🔍 Sample Output

```
======================================================================
IoT Lab Security Testing Framework - Interactive Menu
======================================================================

Available Operations:
--------------------------------------------------
1. Scan subnet for vulnerable devices
2. List discovered vulnerable devices
3. Show discovered credentials
4. Connect to vulnerable device
5. Run coordinated reconnaissance
6. Launch distributed DDoS attack
7. Change scan speed
8. Exit
--------------------------------------------------

Enter your choice (1-8): 1

Enter subnet to scan (e.g., 192.168.1.0/24): 192.168.1.0/24
[INFO] Scanning subnet 192.168.1.0/24 for open Telnet ports...
[+] Found open Telnet on 192.168.1.100
[+] Found open Telnet on 192.168.1.101
[INFO] Found 2 hosts with open Telnet ports

Enter credentials file path (or press Enter for default): 
[INFO] Loaded 20 credential pairs
[INFO] Testing 192.168.1.100...
[+] SUCCESS: 192.168.1.100 - admin:admin
[+] CREDENTIALS: admin:admin
[INFO] Testing 192.168.1.101...
[+] SUCCESS: 192.168.1.101 - ipcamadmin:admin
[+] CREDENTIALS: ipcamadmin:admin

Press Enter to continue...
```

## 🛡️ Security Considerations

### Lab Environment Only
- Use only in isolated, controlled environments
- Never test against production systems
- Ensure proper network isolation
- Document all testing activities

### Rate Limiting
The framework includes built-in rate limiting to prevent overwhelming devices and to simulate realistic attack patterns. Adjust the speed settings as appropriate for your lab environment.

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
   - Check Windows Firewall settings if running in a Windows environment

2. **"No vulnerable devices found":**
   - Verify credentials file format
   - Check if devices use non-standard login prompts
   - Increase timeout values for slow devices
   - Ensure proper network connectivity
   - Try different speed modes

3. **Database errors:**
   - Check file permissions
   - Ensure write permissions to the directory
   - Verify available disk space
   - If using Windows, run as Administrator if needed

4. **Input/Output errors:**
   - In the interactive mode, if you encounter display issues, try resizing your terminal
   - For long-running operations, use the appropriate speed mode for your environment
   - If using Windows PowerShell, ensure console encoding is set correctly

5. **Python-related errors:**
   - Ensure Python 3.8+ is installed: `python --version`
   - Install required packages: `pip install -r requirements.txt`
   - If using a virtual environment, ensure it's activated

### Rollback Option

If you encounter issues with the main interactive script:
- Use the backup version: `python exploit_interactive_backup.py`
- Report any bugs or issues you find

### Performance Tips

- For large networks, start with a faster scan speed to identify devices quickly
- For more thorough testing, switch to normal or slow mode
- When running coordinated attacks, ensure your lab environment can handle the traffic volume
- For improved reliability in virtual environments, adjust the timeout settings

## 📚 Educational Resources

### Recommended Learning Path
1. Set up an isolated lab environment
2. Deploy various IoT device emulations
3. Configure network isolation
4. Run reconnaissance scans using this framework
5. Analyze discovered vulnerabilities and document findings
6. Practice remediation techniques in the lab environment
7. Implement network monitoring and detection rules

## 📄 License

This educational framework is provided for learning purposes. Use responsibly and ethically in controlled environments only.

## ⚖️ Legal Disclaimer

This tool is provided for educational and research purposes only. Users are responsible for complying with all applicable laws and regulations. Only use this tool in environments you own or have explicit permission to test. The authors are not responsible for any misuse of this tool.

---

**Remember**: Always practice ethical hacking and responsible disclosure. This tool is designed to help you learn about IoT security in a safe, controlled environment.
