#!/usr/bin/env python3
"""
IoT Security Research - Network Scanner Module
Educational Purpose Only - For Controlled Lab Environment
"""

import subprocess
import socket
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor


class NetworkScanner:
    """Handles network scanning and device discovery"""
    
    def __init__(self, subnet="11.10.10.0/24", logger=None):
        self.subnet = subnet
        self.logger = logger or logging.getLogger(__name__)
        self.scan_results = []
    
    def log(self, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"[Scanner] {message}")
        print(f"[{timestamp}] {message}")
    
    def scan_network(self):
        """Scan network for vulnerable IoT devices using direct nmap command"""
        try:
            self.log(f"Starting network scan on {self.subnet}")

            # Phase 1: Quick scan for active hosts
            self.log("Phase 1: Quick scan for active hosts...")
            result = subprocess.run([
                "nmap", "-sn", self.subnet
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                self.log(f"Nmap ping scan failed: {result.stderr}")
                return []
                
            output = result.stdout
            active_hosts = []
            for line in output.splitlines():
                if line.startswith("Nmap scan report for"):
                    # Extract IP from line like "Nmap scan report for 192.168.1.1"
                    parts = line.split()
                    if len(parts) >= 5:
                        ip = parts[-1].strip('()')
                        active_hosts.append(ip)
                        
            if not active_hosts:
                self.log("No active hosts found")
                return []
                
            self.log(f"Found {len(active_hosts)} active hosts")

            # Phase 2: Detailed scan of active hosts
            self.log("Phase 2: Detailed scan of active hosts...")
            target_ports = "23,80,443,1883,8883,8080"  # Common IoT ports
            
            for host in active_hosts:
                try:
                    result = subprocess.run([
                        "nmap", "-p", target_ports, "-sV", host
                    ], capture_output=True, text=True, timeout=60)
                    
                    if result.returncode == 0:
                        self._parse_nmap_output(result.stdout, host)
                    else:
                        self.log(f"Port scan failed for {host}: {result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    self.log(f"Timeout scanning {host}")
                except Exception as e:
                    self.log(f"Error scanning {host}: {e}")

            self.log(f"Network scan completed. Found {len(self.scan_results)} potential targets")
            return self.scan_results

        except Exception as e:
            self.log(f"Network scan failed: {e}")
            return []
    
    def _parse_nmap_output(self, output, host):
        """Parse nmap output and extract service information"""
        lines = output.splitlines()
        for line in lines:
            if "/tcp" in line and "open" in line:
                parts = line.split()
                if len(parts) >= 3:
                    port_proto = parts[0]
                    state = parts[1]
                    service = parts[2] if len(parts) > 2 else "unknown"
                    
                    if state == "open":
                        port = int(port_proto.split('/')[0])
                        
                        scan_result = {
                            'ip': host,
                            'port': port,
                            'service': service,
                            'state': state,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        self.scan_results.append(scan_result)
                        self.log(f"Found service: {host}:{port} ({service})")

    def get_scan_results(self):
        """Return current scan results"""
        return self.scan_results
    
    def clear_results(self):
        """Clear scan results"""
        self.scan_results = []
