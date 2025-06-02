#!/usr/bin/env python3
"""
Ubuntu Compatibility Checker and Setup Script
Checks for all required dependencies and installs/compiles C extensions for Ubuntu
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

class UbuntuSetup:
    def __init__(self):
        self.system = platform.system()
        self.is_ubuntu = self.system == "Linux"
        self.missing_packages = []
        self.success_log = []
        self.error_log = []
        
    def log_success(self, message):
        self.success_log.append(f"✅ {message}")
        print(f"✅ {message}")
        
    def log_error(self, message):
        self.error_log.append(f"❌ {message}")
        print(f"❌ {message}")
        
    def log_info(self, message):
        print(f"ℹ️  {message}")
        
    def run_command(self, command, description="", check_output=False):
        """Run a command and handle errors gracefully"""
        try:
            if check_output:
                result = subprocess.run(command, shell=True, capture_output=True, 
                                      text=True, check=True)
                return result.stdout.strip()
            else:
                subprocess.run(command, shell=True, check=True)
                return True
        except subprocess.CalledProcessError as e:
            self.log_error(f"{description} failed: {e}")
            return False
        except Exception as e:
            self.log_error(f"Unexpected error in {description}: {e}")
            return False
    
    def check_system_compatibility(self):
        """Check if running on Ubuntu/Linux"""
        self.log_info(f"Detected system: {self.system}")
        
        if not self.is_ubuntu:
            self.log_info("This script is optimized for Ubuntu/Linux systems")
            self.log_info("On Windows, the existing compiled extensions should work")
            return True
            
        # Check Ubuntu version
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = f.read()
                if 'Ubuntu' in os_info:
                    self.log_success("Ubuntu system detected")
                else:
                    self.log_info("Linux system detected (non-Ubuntu)")
        except:
            self.log_info("Could not determine specific Linux distribution")
            
        return True
    
    def check_python_dev(self):
        """Check Python development headers"""
        try:
            import distutils.sysconfig
            python_inc = distutils.sysconfig.get_python_inc()
            
            if os.path.exists(python_inc):
                self.log_success(f"Python headers found: {python_inc}")
                return True
            else:
                self.log_error("Python development headers not found")
                if self.is_ubuntu:
                    self.missing_packages.append("python3-dev")
                return False
        except Exception as e:
            self.log_error(f"Error checking Python headers: {e}")
            return False
    
    def check_gcc(self):
        """Check GCC compiler"""
        gcc_version = self.run_command("gcc --version", "GCC version check", check_output=True)
        
        if gcc_version:
            self.log_success(f"GCC found: {gcc_version.split()[0]} {gcc_version.split()[3]}")
            return True
        else:
            self.log_error("GCC not found")
            if self.is_ubuntu:
                self.missing_packages.append("build-essential")
            return False
    
    def check_pthread(self):
        """Check pthread library"""
        if not self.is_ubuntu:
            return True  # Skip on non-Linux systems
            
        # Create a temporary test file
        test_code = '''
#include <pthread.h>
#include <stdio.h>
void* test_func(void* arg) { return NULL; }
int main() { 
    pthread_t thread;
    pthread_create(&thread, NULL, test_func, NULL);
    pthread_join(thread, NULL);
    return 0; 
}'''
        
        try:
            with open('/tmp/pthread_test.c', 'w') as f:
                f.write(test_code)
                
            compile_result = self.run_command(
                "gcc /tmp/pthread_test.c -lpthread -o /tmp/pthread_test",
                "pthread compilation test"
            )
            
            if compile_result:
                self.log_success("pthread library available")
                # Clean up
                for f in ['/tmp/pthread_test.c', '/tmp/pthread_test']:
                    try:
                        os.remove(f)
                    except:
                        pass
                return True
            else:
                self.log_error("pthread library not found")
                self.missing_packages.append("libc6-dev")
                return False
                
        except Exception as e:
            self.log_error(f"Error testing pthread: {e}")
            return False
    
    def install_missing_packages(self):
        """Install missing Ubuntu packages"""
        if not self.is_ubuntu or not self.missing_packages:
            return True
            
        self.log_info(f"Installing missing packages: {', '.join(self.missing_packages)}")
        
        # Update package list
        if not self.run_command("sudo apt-get update", "Package list update"):
            return False
            
        # Install packages
        packages_str = ' '.join(self.missing_packages)
        install_cmd = f"sudo apt-get install -y {packages_str}"
        
        if self.run_command(install_cmd, "Package installation"):
            self.log_success(f"Successfully installed: {packages_str}")
            return True
        else:
            self.log_error("Failed to install required packages")
            return False
    
    def compile_c_extensions(self):
        """Compile C extensions for the current platform"""
        extensions = [
            ('fast_telnet_bruteforce', 'setup_fast_bruteforce_cross.py'),
            ('fast_ddos_attack', 'setup_fast_ddos_cross.py')
        ]
        
        compiled_count = 0
        
        for ext_name, setup_script in extensions:
            self.log_info(f"Compiling {ext_name}...")
            
            if self.run_command(f"python3 {setup_script} build_ext --inplace", 
                              f"{ext_name} compilation"):
                self.log_success(f"Successfully compiled {ext_name}")
                compiled_count += 1
            else:
                self.log_error(f"Failed to compile {ext_name}")
        
        return compiled_count == len(extensions)
    
    def test_compiled_extensions(self):
        """Test that compiled extensions can be imported"""
        extensions = ['fast_telnet_bruteforce', 'fast_ddos_attack']
        working_count = 0
        
        for ext_name in extensions:
            try:
                __import__(ext_name)
                self.log_success(f"{ext_name} imports successfully")
                working_count += 1
            except ImportError as e:
                self.log_error(f"Failed to import {ext_name}: {e}")
            except Exception as e:
                self.log_error(f"Unexpected error importing {ext_name}: {e}")
        
        return working_count == len(extensions)
    
    def create_ubuntu_requirements(self):
        """Create Ubuntu-specific requirements file"""
        ubuntu_reqs = """# Ubuntu/Linux Requirements for IoT Digital Twin Attack Threat Scripts

# System Packages (install with apt-get):
# sudo apt-get update
# sudo apt-get install -y build-essential python3-dev libc6-dev

# Python Packages:
requests>=2.28.0
colorama>=0.4.5
concurrent.futures>=3.1.1
threading
socket
time
subprocess
platform

# For C Extension Compilation:
# GCC (included in build-essential)
# Python development headers (python3-dev)
# pthread library (libc6-dev)

# Optional for enhanced performance:
# cython>=0.29.0

# Note: After installing system packages, run:
# python3 setup_fast_bruteforce_cross.py build_ext --inplace
# python3 setup_fast_ddos_cross.py build_ext --inplace
"""
        
        try:
            with open('requirements_ubuntu.txt', 'w') as f:
                f.write(ubuntu_reqs)
            self.log_success("Created requirements_ubuntu.txt")
            return True
        except Exception as e:
            self.log_error(f"Failed to create Ubuntu requirements: {e}")
            return False
    
    def run_full_setup(self):
        """Run complete Ubuntu setup process"""
        print("=" * 70)
        print("🐧 Ubuntu Compatibility Setup for IoT Digital Twin Attack Scripts")
        print("=" * 70)
        
        # Check system compatibility
        if not self.check_system_compatibility():
            return False
            
        # Check all requirements
        self.log_info("Checking system requirements...")
        
        python_ok = self.check_python_dev()
        gcc_ok = self.check_gcc()
        pthread_ok = self.check_pthread()
        
        # Install missing packages if needed
        if self.missing_packages:
            self.log_info(f"Missing packages detected: {', '.join(self.missing_packages)}")
            if not self.install_missing_packages():
                return False
                
            # Re-check after installation
            if not python_ok:
                python_ok = self.check_python_dev()
            if not gcc_ok:
                gcc_ok = self.check_gcc()
            if not pthread_ok:
                pthread_ok = self.check_pthread()
        
        if not all([python_ok, gcc_ok, pthread_ok]):
            self.log_error("Some requirements are still missing after installation")
            return False
        
        # Compile C extensions
        if self.is_ubuntu:
            self.log_info("Compiling C extensions for Ubuntu...")
            if not self.compile_c_extensions():
                self.log_error("C extension compilation failed")
                return False
            
            # Test extensions
            self.log_info("Testing compiled extensions...")
            if not self.test_compiled_extensions():
                self.log_error("Some extensions failed to import")
                return False
        
        # Create Ubuntu requirements
        self.create_ubuntu_requirements()
        
        # Final summary
        print("\n" + "=" * 70)
        print("📊 Setup Summary")
        print("=" * 70)
        
        print("\n✅ Successful operations:")
        for msg in self.success_log:
            print(f"  {msg}")
            
        if self.error_log:
            print("\n❌ Errors encountered:")
            for msg in self.error_log:
                print(f"  {msg}")
        
        if not self.error_log:
            print("\n🎉 Ubuntu setup completed successfully!")
            print("Your system is now ready to run the optimized IoT Digital Twin scripts.")
        else:
            print("\n⚠️  Setup completed with some issues.")
            print("Please review the errors above and resolve them manually.")
        
        print("=" * 70)
        return len(self.error_log) == 0

def main():
    setup = UbuntuSetup()
    return setup.run_full_setup()

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
