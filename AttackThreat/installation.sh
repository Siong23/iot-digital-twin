#!/bin/bash

# AttackThreat Installation Script for Ubuntu
# This script installs all dependencies and Python packages required for the AttackThreat framework

set -e  # Exit on any error

echo "=========================================="
echo "AttackThreat Framework - Ubuntu Installer"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as a regular user."
   exit 1
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install essential build tools and development packages
print_status "Installing essential build tools..."
sudo apt install -y \
    build-essential \
    python3-dev \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget

# Install network tools and libraries
print_status "Installing network tools..."
sudo apt install -y \
    nmap \
    netcat-openbsd \
    telnet \
    openssh-client

# Install cryptography dependencies
print_status "Installing cryptography dependencies..."
sudo apt install -y \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev

# Install MQTT tools
print_status "Installing MQTT tools..."
sudo apt install -y mosquitto-clients

# Create virtual environment
print_status "Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip and setuptools
print_status "Upgrading pip and setuptools..."
pip install --upgrade pip setuptools wheel

# Install Python packages from requirements.txt
print_status "Installing Python packages..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    print_error "requirements.txt not found in current directory!"
    exit 1
fi

# Verify installation
print_status "Verifying installation..."
python3 -c "
try:
    import scapy
    import nmap
    import paramiko
    import paho.mqtt.client as mqtt
    import requests
    print('✓ All critical packages imported successfully')
except ImportError as e:
    print(f'✗ Import error: {e}')
    exit(1)
"

print_status "Installation completed successfully!"
print_warning "IMPORTANT NOTES:"
echo "1. To activate the virtual environment, run: source venv/bin/activate"
echo "2. This framework is for educational and authorized testing purposes only"
echo "3. Always ensure you have proper authorization before using these tools"

echo ""
echo "=========================================="
echo "Installation Summary:"
echo "✓ System packages installed"
echo "✓ Network tools configured"
echo "✓ Python virtual environment created"
echo "✓ Python packages installed"
echo "=========================================="