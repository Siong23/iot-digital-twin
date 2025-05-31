# IoT Digital Twin - Attack & Threat Framework

## Overview

This framework provides tools for IoT security research in controlled lab environments. It consists of a Command and Control (C2) server and an exploit script that can discover vulnerable IoT devices, exploit them through telnet brute-forcing, and coordinate distributed attacks.

## Educational Purpose

This software is designed for educational and research purposes in controlled lab environments only. It should never be used against systems without explicit authorization.

## Components

1. **C2 Server** - Central command server that manages compromised devices
2. **Exploit Script** - Tool for discovering and exploiting vulnerable devices
3. **Bot Client** - Simulated IoT bot for testing purposes

## Quick Start

### Windows Users

#### Starting the C2 Server

1. Run the setup and start script:
   ```
   start_c2_server.bat
   ```

   This will install all required dependencies and start the C2 server.

2. The C2 server web interface will be available at:
   ```
   http://127.0.0.1:5000
   ```

#### Running the Exploit Script

1. Run the exploit script:
   ```
   run_exploit.bat [C2_SERVER_IP] [TARGET_SUBNET]
   ```

   For example:
   ```
   run_exploit.bat 127.0.0.1 192.168.1.0/24
   ```

### Linux/Ubuntu Users

#### Starting the C2 Server

1. Make the scripts executable:
   ```
   chmod +x *.sh
   ```

2. Run the setup and start script:
   ```
   ./start_c2_server.sh
   ```

   This will install all required dependencies and start the C2 server.

3. The C2 server web interface will be available at:
   ```
   http://127.0.0.1:5000
   ```

#### Running the Exploit Script

1. Run the exploit script:
   ```
   ./run_exploit.sh [C2_SERVER_IP] [TARGET_SUBNET]
   ```

   For example:
   ```
   ./run_exploit.sh 127.0.0.1 192.168.1.0/24
   ```

2. Use the interactive menu in the exploit script to:
   - Scan networks for vulnerable devices
   - Brute-force telnet credentials
   - Launch DDoS attacks via the C2 server
   - Save and export results

### Testing the System

#### Windows
```
test_system.bat
```

#### Linux/Ubuntu
```
./test_system.sh
```

## Requirements

- Python 3.9 or later
- Network access to the target IoT devices
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
