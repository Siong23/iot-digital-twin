import os
import platform

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def print_banner():
    """Print application banner"""
    clear_screen()
    banner = f"""{Colors.CYAN}
╔══════════════════════════════════════════════╗
║           IoT Attack Simulation              ║
║              Lab Environment                 ║
║                                              ║
║  🔍 Discovery  🔓 Compromise  🦠 Infection   ║
║             🚀 DDoS Control                  ║
╚══════════════════════════════════════════════╝
{Colors.RESET}"""
    print(banner)
