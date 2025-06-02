#!/usr/bin/env python3
"""
Cross-Platform Setup Script for Fast DDoS Attack C Extension
Supports both Windows and Linux/Ubuntu
"""

import os
import sys
import platform
import subprocess
from distutils.core import setup, Extension

def check_requirements():
    """Check if all required tools are available"""
    system = platform.system()
    print(f"Detected system: {system}")
    
    # Check Python development headers
    try:
        import distutils.util
        import distutils.sysconfig
        python_inc = distutils.sysconfig.get_python_inc()
        print(f"Python include directory: {python_inc}")
    except Exception as e:
        print(f"Error getting Python include directory: {e}")
        return False
    
    # Check GCC
    try:
        result = subprocess.run(['gcc', '--version'], 
                              capture_output=True, text=True, check=True)
        gcc_version = result.stdout.split('\n')[0]
        print(f"GCC found: {gcc_version}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: GCC not found!")
        if system == "Linux":
            print("On Ubuntu/Debian, install with: sudo apt-get install build-essential")
            print("On CentOS/RHEL, install with: sudo yum groupinstall 'Development Tools'")
        elif system == "Windows":
            print("On Windows, install MinGW-w64 or Microsoft Visual C++")
        return False
    
    # Check pthread on Linux
    if system == "Linux":
        try:
            result = subprocess.run(['gcc', '-lpthread', '-xc', '/dev/null', '-o', '/dev/null'], 
                                  capture_output=True, check=True)
            print("pthread library found")
        except subprocess.CalledProcessError:
            print("ERROR: pthread development library not found!")
            print("On Ubuntu/Debian, install with: sudo apt-get install libc6-dev")
            return False
    
    return True

def get_compile_args():
    """Get platform-specific compile arguments"""
    system = platform.system()
    
    if system == "Windows":
        return {
            'extra_compile_args': ['-O3', '-Wall', '-std=c99'],
            'extra_link_args': ['-lws2_32'],
            'libraries': ['ws2_32']
        }
    else:  # Linux/Unix
        return {
            'extra_compile_args': ['-O3', '-Wall', '-std=c99', '-fPIC'],
            'extra_link_args': ['-lpthread'],
            'libraries': ['pthread']
        }

def main():
    print("=" * 60)
    print("Fast DDoS Attack C Extension - Cross-Platform Setup")
    print("=" * 60)
    
    if not check_requirements():
        print("\nSetup failed: Missing required dependencies")
        sys.exit(1)
    
    # Get platform-specific arguments
    compile_args = get_compile_args()
    
    # Define the extension
    ddos_attack_ext = Extension(
        'fast_ddos_attack',
        sources=['fast_ddos_attack_cross.c'],
        **compile_args
    )
    
    print("\nBuilding C extension...")
    
    setup(
        name='fast_ddos_attack',
        version='1.0',
        description='High-performance DDoS attack module',
        ext_modules=[ddos_attack_ext],
        zip_safe=False
    )
    
    print("\n" + "=" * 60)
    print("Build completed successfully!")
    print("The extension should now be available for import.")
    print("=" * 60)

if __name__ == '__main__':
    main()
