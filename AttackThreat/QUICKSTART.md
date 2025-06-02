# 🚀 Quick Start Guide - IoT Attack Simulation Framework

## ⚠️ **IMPORTANT**: This is for isolated lab environments ONLY!

## 📖 How to Run

### Method 1: PowerShell Script (Recommended)
```powershell
# Allow script execution (run once)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Navigate to project directory
cd "d:\MMU\FYP\attack"

# Run the PowerShell launcher
.\run.ps1
```

### Method 2: Batch File
```cmd
# Double-click run.bat or run from command prompt
.\run.bat
```

### Method 3: Direct Python Execution
```powershell
# Navigate to project directory
cd "d:\MMU\FYP\attack"

# Install dependencies
python -m pip install python-nmap paramiko telnetlib3

# Run the framework
python main.py
```

## 🎯 Demo Workflow

Follow this sequence to see the complete attack simulation:

### 1. 🔍 Network Discovery
- Select option **1** from the menu
- Enter a target network: `192.168.1.0/24` (or your lab network)
- The scanner will discover devices with open ports
- Demo targets are automatically added for testing

### 2. 🔓 Brute Force Attack
- Select option **2** from the menu
- Choose a target IP from the discovered devices
- Watch as the system tests common IoT credentials:
  - `admin:admin`
  - `root:root` 
  - `ipcamadmin:admin`
  - `temphumidadmin:admin`
  - And many more...

### 3. 🦠 Deploy Bot Infection
- Select option **3** from the menu
- Choose to deploy to all compromised devices
- The system will simulate bot deployment:
  - Upload bot client script
  - Install hping3 dependencies
  - Start bot service

### 4. 🚀 Launch DDoS Attack
- Select option **4** from the menu
- Enter target IP (e.g., `10.0.0.100`)
- Choose attack type:
  - **syn** - SYN flood attack
  - **rtsp** - RTSP service flood
  - **mqtt** - MQTT broker flood

### 5. 📊 Monitor Status
- Select option **6** to view active attacks
- See real-time status of infected devices
- Monitor attack duration and participating bots

### 6. ⏹️ Stop Attacks
- Select option **5** to stop all active attacks
- System will gracefully terminate all attack processes

### 7. 📋 View Logs
- Select option **7** to see complete database logs
- Review all discovered devices, compromised credentials, and attack history

## 💾 Database Storage

All data is stored in `research_db.sqlite` with tables for:
- **discovered_devices** - Network scan results
- **compromised_devices** - Successful login attempts  
- **infected_devices** - Bot-infected systems
- **attack_logs** - DDoS attack history

## 🛠️ Customization

### Add Custom Credentials
Edit `modules/bruteforce.py`:
```python
self.credentials = [
    ('admin', 'admin'),
    ('your_username', 'your_password'),
    # Add more credentials here
]
```

### Modify Attack Types
Edit `modules/ddos_control.py` to add new attack methods.

### Change Target Ports
Edit `modules/scanner.py`:
```python
ports = [22, 23, 80, 554, 1883, 8080, YOUR_PORT]
```

## 🔧 Troubleshooting

### Common Issues:

**1. Python Import Errors**
```powershell
# Reinstall dependencies
python -m pip install --upgrade python-nmap paramiko telnetlib3
```

**2. PowerShell Execution Policy**
```powershell
# Allow script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**3. Nmap Not Found**
- Download and install Nmap from: https://nmap.org/download.html
- The framework includes fallback scanning methods

**4. Permission Denied**
- Run PowerShell/Command Prompt as Administrator
- Ensure antivirus isn't blocking the framework

## ⚡ Features Demonstrated

✅ **Network Reconnaissance** - Discover IoT devices  
✅ **Credential Testing** - Brute force weak passwords  
✅ **Botnet Simulation** - Deploy and control bots  
✅ **DDoS Coordination** - Launch synchronized attacks  
✅ **Real-time Monitoring** - Track attack status  
✅ **Data Persistence** - SQLite database logging  
✅ **Graceful Shutdown** - Ctrl+C handling  
✅ **Cross-platform** - Windows/Linux compatible  

## 🎓 Educational Value

This framework teaches:
- IoT vulnerability assessment
- Common attack vectors and methodologies
- Botnet command and control structures
- Network reconnaissance techniques
- DDoS attack coordination
- Cybersecurity defensive strategies

## 📞 Support

If you encounter issues:
1. Check the terminal output for error messages
2. Verify Python and pip are working correctly
3. Ensure all dependencies are installed
4. Try running individual modules for debugging

---

**Remember: Use responsibly in isolated lab environments only!** 🔒
