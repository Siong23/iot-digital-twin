# C2 Server Architecture Documentation

## Overview

This document describes the architecture and component relationships of the Command and Control (C2) server implementation for the IoT security research project. The server is designed for educational and research purposes in a controlled lab environment.

## Architecture

The C2 server has been refactored into a modular structure with the following components:

### Directory Structure

```
AttackThreat/
├── bot_client.py       - Bot client implementation
├── c2_server.py        - Parent runner script
├── exploit.py          - Exploitation script
└── c2_server/          - Modular C2 server implementation
    ├── __init__.py     - Package marker
    ├── c2_server.py    - Main server application with Flask routes
    ├── db_manager.py   - Database management
    ├── tn_manager.py   - Telnet connection management
    ├── web_ui.py       - Web interface and dashboard
    └── run_c2.py       - Simple runner script
```

### Component Relationships

1. **Parent Runner Script (`c2_server.py`)**
   - Entry point for running the C2 server
   - Imports and runs the Flask application from the modular structure

2. **Main Server Application (`c2_server/c2_server.py`)**
   - Contains all Flask routes and API endpoints
   - Manages global state like active attacks
   - Coordinates between different components

3. **Database Manager (`c2_server/db_manager.py`)**
   - Handles all database operations
   - Manages device registration, command logging, and attack logs
   - Provides thread-safe access to the SQLite database

4. **Telnet Manager (`c2_server/tn_manager.py`)**
   - Manages telnet connections to compromised devices
   - Handles authentication and command execution
   - Maintains session tracking

5. **Web UI (`c2_server/web_ui.py`)**
   - Provides the web interface for the C2 server
   - Renders the dashboard with device status and attack information
   - Contains HTML templates for the UI

6. **Runner Script (`c2_server/run_c2.py`)**
   - Simple script to run the C2 server directly from the module

### Client Applications

1. **Bot Client (`bot_client.py`)**
   - Simulates a compromised IoT device
   - Connects to the C2 server and executes commands
   - Performs attacks as directed by the server

2. **Exploit Script (`exploit.py`)**
   - Scans for vulnerable IoT devices
   - Attempts to compromise devices using brute force
   - Registers compromised devices with the C2 server

## API Endpoints

The server exposes the following API endpoints:

- `/` - Main dashboard UI
- `/bot-checkin` - Endpoint for bots to check in with the server
- `/get-command/{bot_id}` - Endpoint for bots to get commands
- `/start-attack` - Start an attack on a target
- `/stop-attack` - Stop an ongoing attack
- `/get-scan-results` - Get scan results from the database
- `/get-compromised-devices` - Get a list of compromised devices

## Running the Server

There are two ways to run the C2 server:

### 1. Using the parent runner script

From the AttackThreat directory:
```
python c2_server.py
```

This method is preferred as it properly sets up the Python path and ensures all imports work correctly.

### 2. Using the module's runner script

From the AttackThreat directory:
```
cd c2_server
python run_c2.py
```

Both methods start the server with the same configuration, binding to all interfaces (0.0.0.0) on port 5000.

## Security Notice

This server implementation is designed for educational and research purposes only in a controlled lab environment. It should never be deployed on a public network or used for any malicious activities.
