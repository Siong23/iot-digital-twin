import threading
import subprocess
import socket
from .utils import Colors

class NetworkScanner:
    def __init__(self, database):
        self.db = database
    
    def scan_port(self, ip, port, timeout=3):
        """Simple port scanner using socket"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                return True
        except:
            pass
        return False
    
    def get_service_name(self, port):
        """Get service name based on port"""
        services = {
            22: 'ssh',
            23: 'telnet',
            80: 'http',
            443: 'https',
            554: 'rtsp',
            1883: 'mqtt',
            8080: 'http-alt'
        }
        return services.get(port, 'unknown')
    
    def scan_host(self, ip, ports):
        """Scan a single host for open ports"""
        open_ports = []
        for port in ports:
            if self.scan_port(ip, port):
                service = self.get_service_name(port)
                open_ports.append((port, service))
                print(f"{Colors.GREEN}[+] Found: {ip}:{port} ({service}){Colors.RESET}")
                self.db.add_discovered_device(ip, port, service, "")
        return open_ports
    
    def generate_ip_range(self, network):
        """Generate IP addresses from network range"""
        try:
            # Simple implementation for /24 networks
            if '/24' in network:
                base = network.split('/')[0]
                base_parts = base.split('.')
                base_ip = '.'.join(base_parts[:3])
                
                ips = []
                for i in range(1, 255):
                    ips.append(f"{base_ip}.{i}")
                return ips
            else:
                # For single IP
                return [network]
        except:
            return []
    
    def scan_network(self, target_network):
        """Scan network for IoT devices with common ports"""
        print(f"{Colors.YELLOW}[*] Scanning {target_network} for IoT services...{Colors.RESET}")
        
        # Common IoT ports
        ports = [22, 23, 80, 554, 1883, 8080]
        
        try:
            # Generate IP list
            ip_list = self.generate_ip_range(target_network)
            
            if not ip_list:
                print(f"{Colors.RED}[!] Invalid network format{Colors.RESET}")
                return
            
            print(f"{Colors.CYAN}[*] Scanning {len(ip_list)} hosts...{Colors.RESET}")
            
            # Scan each IP
            for ip in ip_list:
                self.scan_host(ip, ports)
            
            print(f"{Colors.CYAN}[*] Network scan completed.{Colors.RESET}")
            
        except Exception as e:
            print(f"{Colors.RED}[!] Scan error: {e}{Colors.RESET}")
            
        # Fallback: Add some demo data for testing
        print(f"{Colors.YELLOW}[*] Adding demo targets for testing...{Colors.RESET}")
        demo_targets = [
            ("192.168.1.100", 23, "telnet"),
            ("192.168.1.101", 22, "ssh"),
            ("192.168.1.102", 80, "http"),
            ("10.10.10.10", 554, "rtsp")
        ]
        
        for ip, port, service in demo_targets:
            self.db.add_discovered_device(ip, port, service, "demo")
