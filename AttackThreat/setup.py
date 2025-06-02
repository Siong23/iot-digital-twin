#!/usr/bin/env python3
"""
Setup script for IoT Attack Simulation Framework
"""

import os
import sys
import subprocess

def install_requirements():
    """Install required Python packages"""
    try:
        print("📦 Installing Python requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Python requirements installed successfully")
    except Exception as e:
        print(f"❌ Failed to install requirements: {e}")
        print("💡 Try running: pip install python-nmap paramiko telnetlib3")

def create_directories():
    """Create necessary directories"""
    dirs = ["bot_templates", "logs"]
    for dir_name in dirs:
        os.makedirs(dir_name, exist_ok=True)
        print(f"✅ Created directory: {dir_name}")

def check_nmap():
    """Check if Nmap is installed"""
    try:
        subprocess.run(["nmap", "--version"], capture_output=True, check=True)
        print("✅ Nmap is installed")
    except:
        print("⚠️  Nmap not found. Please install Nmap for full functionality:")
        print("   Download from: https://nmap.org/download.html")

def main():
    print("🔧 Setting up IoT Attack Simulation Framework...")
    print("=" * 50)
    
    create_directories()
    install_requirements()
    check_nmap()
    
    print("=" * 50)
    print("✅ Setup completed!")
    print("📖 To run the simulation:")
    print("   python main.py")
    print("")
    print("⚠️  Remember: This is for isolated lab environments only!")

if __name__ == "__main__":
    main()
