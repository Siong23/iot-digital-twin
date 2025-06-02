# IoT Attack Simulation Framework
## Digital Twin Network Security Testbed

### 🎯 **Research Overview**
This framework provides a comprehensive IoT attack simulation environment designed for cybersecurity research and education. It demonstrates the complete attack lifecycle: **Discovery → Compromise → Control → Exploitation** against IoT devices in a controlled digital twin network testbed.

## ⚠️ **IMPORTANT DISCLAIMER**
This framework is designed **EXCLUSIVELY** for isolated lab environments and educational purposes. **DO NOT** use this on production networks or systems you do not own.

## 🌐 **Digital Twin Testbed Integration**
This simulation framework is designed to work with GNS3-based IoT network testbeds. For the complete digital twin IoT security testbed setup, refer to:
- **Testbed Repository**: [IoT Digital Twin Testbed](https://github.com/Siong23/iot-digital-twin)
- **GNS3 Network Topology**: Based on the network diagram provided
- **Target Environment**: Ubuntu 22.04.4 LTS with KVM support

## 📋 **Attack Simulation Features**

- **🔍 Network Discovery**: Comprehensive IoT device scanning with service detection
- **🔓 Brute Force Attacks**: Test 17+ common IoT credential combinations
- **🦠 Bot Deployment**: Deploy lightweight malware clients on compromised devices
- **🚀 DDoS Control**: Coordinate SYN flood, RTSP flood, and MQTT flood attacks
- **📊 Real-time Monitoring**: Track attack progress and infected device status
- **💾 Database Logging**: Persistent SQLite storage for research data analysis
- **🛡️ Graceful Controls**: Safe start/stop mechanisms with Ctrl+C handling

## 🏗️ **Prerequisites & Installation (Ubuntu)**

### **System Requirements**
- **OS**: Ubuntu 22.04.4 LTS (recommended)
- **Python**: 3.8+ with pip package manager
- **Memory**: 4GB RAM minimum (8GB recommended)
- **Network**: Isolated lab environment with target IoT devices
- **Privileges**: sudo access for package installation

### **Core Dependencies**
```bash
# System packages
sudo apt update
sudo apt install -y python3 python3-pip nmap git

# Python packages (auto-installed by framework)
python3-nmap>=1.4.6
paramiko>=2.7.2
telnetlib3>=1.0.2
```

### **Optional Dependencies for Full Testbed**
```bash
# GNS3 and virtualization
sudo apt install -y gns3-gui gns3-server
sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils

# Docker for IoT device simulation
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER

# Additional network tools
sudo apt install -y wireshark tshark tcpdump
sudo apt install -y hping3 netcat-openbsd
```

### **GNS3 Testbed Components** (Optional)
- [Cisco 7200 Router Image](https://www.gns3.com/marketplace/appliances/cisco-7200)
- Open vSwitch (fixed version)
- Ubuntu Server VMs
- Kali Linux for GNS3
- Ubuntu Guest Additions

### **Installation Steps**

#### Method 1: Automated Setup (Recommended)
```bash
# Clone or download the framework
cd /path/to/attack/framework

# Run setup script
chmod +x setup.py
python3 setup.py

# Verify installation
python3 main.py --help
```

#### Method 2: Manual Installation
```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Install system dependencies
sudo apt install -y nmap python3-nmap

# Verify installation
python3 --version
python3 -c "import nmap, paramiko, telnetlib3; print('Dependencies OK')"

# Test nmap functionality
nmap --version
```

#### Method 3: Development Setup
```bash
# Create virtual environment (recommended for development)
python3 -m venv venv
source venv/bin/activate

# Install dependencies in virtual environment
pip install -r requirements.txt

# Install additional development tools
pip install pytest black flake8

# Run tests (if available)
python3 -m pytest tests/
```

## 🚀 **Usage**

### **Start the Framework**
```bash
# Navigate to framework directory
cd /path/to/attack/framework

# Run the main application
python3 main.py
```

### **Menu Options:**

1. **🔍 Network Discovery Scan** - Discover IoT devices
2. **🔓 Brute Force Attack** - Test credentials on discovered devices  
3. **🦠 Deploy Bot Infection** - Install bot clients on compromised devices
4. **🚀 Start DDoS Attack** - Launch coordinated attacks
5. **⏹️ Stop DDoS Attack** - Stop all active attacks
6. **📊 Show Attack Status** - View current attack status
7. **📋 View Database Logs** - Review all logged activities
8. **🧹 Clear Database** - Reset all stored data
9. **❌ Exit** - Quit the framework

### **Example Usage Session**
```bash
# 1. Start the framework
python3 main.py

# 2. In the menu, select option 1 (Network Discovery)
# Enter target: 192.168.1.0/24

# 3. Select option 2 (Brute Force)
# Enter target IP from discovered devices

# 4. Select option 3 (Deploy Bots)
# Confirm deployment to compromised devices

# 5. Select option 4 (Start DDoS)
# Enter target IP and attack type (syn/rtsp/mqtt)

# 6. Select option 6 (Show Status)
# Monitor attack progress

# 7. Select option 5 (Stop Attack)
# Gracefully stop all attacks
```

## 📁 **Project Structure**

```
attack/
├── main.py                 # Main application controller
├── requirements.txt        # Python dependencies
├── setup.py               # Setup and installation script
├── research_db.sqlite     # Database file (created on first run)
├── modules/               # Core modules
│   ├── __init__.py
│   ├── utils.py          # Utilities and colors
│   ├── database.py       # Database management
│   ├── scanner.py        # Network scanning
│   ├── bruteforce.py     # Credential testing
│   ├── infection.py      # Bot deployment
│   └── ddos_control.py   # Attack coordination
├── bot_templates/         # Bot client templates
│   └── bot_client.sh     # Bash bot script
└── logs/                 # Log files directory
```

## 🛡️ **Security Features**

- **Graceful Ctrl+C handling** - Clean shutdown
- **Database transaction safety** - Prevents corruption
- **Error handling** - Robust exception management
- **Modular design** - Easy to modify and extend

## 📝 **Example Workflow**

```bash
# 1. Network Discovery
Target Network: 192.168.1.0/24
Expected Results: IP cameras, sensors, routers with open ports

# 2. Credential Testing
Target: 192.168.1.100:23 (Telnet)
Credentials: admin:admin, root:root, etc.

# 3. Bot Deployment
Deploy to: All compromised devices
Install: Lightweight bot client with hping3

# 4. DDoS Attack
Target: 192.168.1.200
Type: SYN flood
Bots: All infected devices

# 5. Monitoring
Status: Real-time attack progress
Database: All activities logged automatically
```

## 🔧 **Customization**

### **Add New Credentials**
```bash
# Edit modules/bruteforce.py
nano modules/bruteforce.py

# Add to credentials list:
('newuser', 'newpass'),
('iotdevice', 'default123'),
```

### **Modify Scan Ports**
```bash
# Edit modules/scanner.py
nano modules/scanner.py

# Update port list:
results = self.nm.scan(target_network, '22,23,80,554,8080,1883', '-sS -T4')
```

### **Custom Attack Types**
```bash
# Edit modules/ddos_control.py
nano modules/ddos_control.py

# Add new attack function
def custom_flood(self, target_ip):
    # Your custom attack implementation
```

## 📊 **Research Database Schema**

The framework creates a comprehensive SQLite database (`research_db.sqlite`) with four main tables:

### **Database Tables**
```sql
-- Network reconnaissance results
discovered_devices (id, ip_address, port, service, banner, timestamp)

-- Successful credential attacks
compromised_devices (id, ip_address, port, username, password, service, timestamp)

-- Botnet infection tracking
infected_devices (id, ip_address, status, bot_version, last_contact, timestamp)

-- DDoS attack coordination logs
attack_logs (id, attack_type, target_ip, source_devices, status, start_time, end_time)
```

### **Data Analysis Examples**
```bash
# View database contents
sqlite3 research_db.sqlite

# Example queries:
.tables
SELECT * FROM discovered_devices;
SELECT COUNT(*) FROM compromised_devices;
SELECT * FROM attack_logs WHERE status='active';
```

## ⚡ **Technical Notes**

- **Database**: SQLite for data persistence and research analysis
- **Interruption**: Supports graceful interruption (Ctrl+C)
- **Architecture**: Modular design for easy extension
- **Bot Installation**: Auto-detects and installs hping3 on target devices
- **Network Tools**: Uses nmap for discovery, telnetlib for connection
- **Attack Tools**: Leverages hping3 for DDoS simulation

## 🎯 **Lab Environment Setup**

### **Digital Twin Testbed Architecture**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Gateway       │────│  Digital Router  │────│  IoT Devices    │
│   DigitalTwin   │    │                  │    │  - IP Cameras   │
│                 │    │                  │    │  - Sensors      │
└─────────────────┘    └──────────────────┘    │  - Controllers  │
                                               └─────────────────┘
```

### **Ubuntu Lab Setup Steps**
```bash
# 1. Install GNS3 (optional)
sudo add-apt-repository ppa:gns3/ppa
sudo apt update
sudo apt install gns3-gui gns3-server

# 2. Configure virtualization
sudo usermod -aG kvm $USER
sudo usermod -aG libvirt $USER

# 3. Setup isolated network
sudo brctl addbr lab-br0
sudo ip addr add 192.168.100.1/24 dev lab-br0
sudo ip link set lab-br0 up

# 4. Deploy IoT simulators
docker run -d --name iot-camera --network lab-net vulnerable-ipcam
docker run -d --name iot-sensor --network lab-net mqtt-sensor

# 5. Start attack framework
cd /path/to/attack/framework
python3 main.py
```

### **Target Device Recommendations**
- **IP Cameras**: Vulnerable RTSP streams with default credentials
- **MQTT Brokers**: Unsecured message brokers
- **IoT Sensors**: Temperature/humidity devices with Telnet access
- **Smart Controllers**: Home automation devices
- **Network Equipment**: Routers/switches with web interfaces

## 📚 **Educational & Research Value**

### **Cybersecurity Concepts Demonstrated**
- **IoT Vulnerability Assessment**: Common weaknesses in IoT devices
- **Attack Vector Analysis**: Multiple entry points and escalation paths
- **Botnet Operations**: Command and control infrastructure simulation
- **Network Reconnaissance**: Automated discovery and enumeration
- **Credential Security**: Password policy enforcement importance
- **DDoS Attack Coordination**: Distributed attack orchestration
- **Digital Forensics**: Attack artifact collection and analysis

### **Research Applications**
- **Threat Modeling**: Understanding IoT attack surfaces
- **Defense Testing**: Validating security controls effectiveness
- **Incident Response**: Attack simulation for response team training
- **Security Awareness**: Demonstrating real-world attack scenarios
- **Academic Research**: Publishable IoT security vulnerability studies

## 🔗 **References & Resources**

### **Technical Documentation**
- [MQTT Broker Security Setup](https://medium.com/gravio-edge-iot-platform/how-to-set-up-a-mosquitto-mqtt-broker-securely-using-client-certificates-82b2aaaef9c8)
- [GNS3 Network Simulation Guide](https://www.gns3.com/marketplace/appliances/cisco-7200)
- [IoT Security Testing Methodology](https://github.com/Siong23/iot-digital-twin)

### **Ubuntu-Specific Resources**
- [Ubuntu Server Guide](https://ubuntu.com/server/docs)
- [KVM Virtualization on Ubuntu](https://help.ubuntu.com/community/KVM)
- [Docker Installation on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Python Development on Ubuntu](https://ubuntu.com/server/docs/programming-python)

## ⚠️ **Legal Notice & Ethical Guidelines**

### **Authorized Use Only**
This tool is for **EDUCATIONAL and RESEARCH purposes ONLY**. Users must:
- Use only in isolated, controlled laboratory environments
- Obtain proper authorization before testing any systems
- Comply with all applicable laws and regulations
- Follow responsible disclosure practices
- Respect intellectual property and privacy rights

### **Prohibited Activities**
- **DO NOT** use on production networks or systems you do not own
- **DO NOT** use for malicious purposes or unauthorized access
- **DO NOT** distribute malware or cause system damage
- **DO NOT** violate any applicable laws or regulations

## 🤝 **Contributing & Support**

### **Development Environment Setup**
```bash
# Fork and clone repository
git clone https://github.com/your-repo/iot-attack-simulation
cd iot-attack-simulation

# Create development environment
python3 -m venv dev-env
source dev-env/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest black flake8

# Run tests
python3 -m pytest tests/

# Format code
black .
flake8 .
```

### **Bug Reports & Feature Requests**
- **Issues**: Submit detailed reports with Ubuntu version and logs
- **Features**: Suggest improvements for Ubuntu-specific functionality
- **Documentation**: Help improve Ubuntu setup instructions
- **Testing**: Contribute Ubuntu compatibility testing

---

### 🔒 **Remember: Always use responsibly in controlled Ubuntu lab environments only!**

*This framework is optimized for Ubuntu-based cybersecurity research environments and educational IoT security testing.*
