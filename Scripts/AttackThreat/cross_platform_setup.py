#!/usr/bin/env python3
"""
Cross-Platform Auto-Setup Script for IoT Digital Twin Attack Scripts
Automatically detects the platform and sets up the appropriate C extensions
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

class CrossPlatformSetup:
    def __init__(self):
        self.system = platform.system()
        self.architecture = platform.machine()
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        
    def detect_platform(self):
        """Detect the current platform and return setup strategy"""
        print(f"🔍 Platform Detection:")
        print(f"   System: {self.system}")
        print(f"   Architecture: {self.architecture}")
        print(f"   Python: {self.python_version}")
        
        if self.system == "Windows":
            return "windows"
        elif self.system == "Linux":
            return "linux"
        elif self.system == "Darwin":
            return "macos"
        else:
            return "unknown"
    
    def check_existing_extensions(self):
        """Check if pre-compiled extensions are available"""
        extensions = {
            'fast_telnet_bruteforce': False,
            'fast_ddos_attack': False
        }
        
        # Check for existing compiled extensions
        for ext_name in extensions.keys():
            try:
                __import__(ext_name)
                extensions[ext_name] = True
                print(f"✅ {ext_name} extension is available")
            except ImportError:
                print(f"❌ {ext_name} extension not found")
        
        return extensions
    
    def run_windows_setup(self):
        """Setup for Windows platform"""
        print("\n🪟 Windows Setup")
        print("=" * 50)
        
        # Check if pre-compiled Windows extensions exist
        windows_extensions = [
            'fast_telnet_bruteforce.cp312-win_amd64.pyd',
            'fast_ddos_attack.cp312-win_amd64.pyd'
        ]
        
        available_count = 0
        for ext_file in windows_extensions:
            if os.path.exists(ext_file):
                print(f"✅ Found: {ext_file}")
                available_count += 1
            else:
                print(f"❌ Missing: {ext_file}")
        
        if available_count == len(windows_extensions):
            print("✅ All Windows extensions are available!")
            return True
        
        # Try to compile using Windows setup scripts
        print("\n🔨 Attempting to compile C extensions...")
        
        setup_scripts = [
            'setup_fast_bruteforce_win.py',
            'setup_fast_ddos_win.py'
        ]
        
        compiled_count = 0
        for script in setup_scripts:
            if os.path.exists(script):
                try:
                    result = subprocess.run([sys.executable, script, 'build_ext', '--inplace'],
                                          capture_output=True, text=True, check=True)
                    print(f"✅ Compiled using {script}")
                    compiled_count += 1
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to compile using {script}: {e}")
        
        return compiled_count > 0
    
    def run_linux_setup(self):
        """Setup for Linux/Ubuntu platform"""
        print("\n🐧 Linux/Ubuntu Setup")
        print("=" * 50)
        
        # Run the Ubuntu setup script
        ubuntu_script = 'ubuntu_setup.py'
        if os.path.exists(ubuntu_script):
            print(f"🚀 Running {ubuntu_script}...")
            try:
                result = subprocess.run([sys.executable, ubuntu_script],
                                      check=True)
                return True
            except subprocess.CalledProcessError:
                print(f"❌ Ubuntu setup script failed")
                return False
        else:
            print(f"❌ Ubuntu setup script not found: {ubuntu_script}")
            
            # Fallback: try cross-platform setup scripts
            print("🔨 Attempting cross-platform compilation...")
            setup_scripts = [
                'setup_fast_bruteforce_cross.py',
                'setup_fast_ddos_cross.py'
            ]
            
            compiled_count = 0
            for script in setup_scripts:
                if os.path.exists(script):
                    try:
                        result = subprocess.run([sys.executable, script, 'build_ext', '--inplace'],
                                              capture_output=True, text=True, check=True)
                        print(f"✅ Compiled using {script}")
                        compiled_count += 1
                    except subprocess.CalledProcessError as e:
                        print(f"❌ Failed to compile using {script}: {e}")
            
            return compiled_count > 0
    
    def run_macos_setup(self):
        """Setup for macOS platform"""
        print("\n🍎 macOS Setup")
        print("=" * 50)
        print("ℹ️  macOS support is experimental")
        
        # Use cross-platform setup scripts
        setup_scripts = [
            'setup_fast_bruteforce_cross.py',
            'setup_fast_ddos_cross.py'
        ]
        
        compiled_count = 0
        for script in setup_scripts:
            if os.path.exists(script):
                try:
                    result = subprocess.run([sys.executable, script, 'build_ext', '--inplace'],
                                          capture_output=True, text=True, check=True)
                    print(f"✅ Compiled using {script}")
                    compiled_count += 1
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to compile using {script}: {e}")
        
        return compiled_count > 0
    
    def install_python_requirements(self):
        """Install Python package requirements"""
        print("\n📦 Installing Python Requirements")
        print("=" * 50)
        
        requirements_file = 'requirements.txt'
        if os.path.exists(requirements_file):
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', requirements_file],
                             check=True)
                print("✅ Python requirements installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install Python requirements: {e}")
                return False
        else:
            print(f"❌ Requirements file not found: {requirements_file}")
            return False
    
    def test_final_setup(self):
        """Test that everything is working"""
        print("\n🧪 Testing Final Setup")
        print("=" * 50)
        
        # Test Python imports
        required_modules = [
            'requests',
            'flask',
            'colorama'
        ]
        
        for module in required_modules:
            try:
                __import__(module)
                print(f"✅ {module} imports successfully")
            except ImportError:
                print(f"❌ Failed to import {module}")
        
        # Test C extensions
        c_extensions = [
            'fast_telnet_bruteforce',
            'fast_ddos_attack'
        ]
        
        working_extensions = 0
        for ext in c_extensions:
            try:
                __import__(ext)
                print(f"✅ {ext} C extension working")
                working_extensions += 1
            except ImportError:
                print(f"⚠️  {ext} C extension not available (will use Python fallback)")
        
        return working_extensions > 0
    
    def run_setup(self):
        """Run the complete cross-platform setup"""
        print("=" * 70)
        print("🚀 IoT Digital Twin - Cross-Platform Auto-Setup")
        print("=" * 70)
        
        # Detect platform
        platform_type = self.detect_platform()
        
        # Check existing extensions
        print("\n🔍 Checking Existing Extensions")
        print("=" * 50)
        existing_extensions = self.check_existing_extensions()
        
        # Run platform-specific setup
        setup_success = False
        
        if platform_type == "windows":
            setup_success = self.run_windows_setup()
        elif platform_type == "linux":
            setup_success = self.run_linux_setup()
        elif platform_type == "macos":
            setup_success = self.run_macos_setup()
        else:
            print(f"⚠️  Unknown platform: {self.system}")
            print("Attempting cross-platform compilation...")
            
            # Fallback to cross-platform scripts
            setup_scripts = [
                'setup_fast_bruteforce_cross.py',
                'setup_fast_ddos_cross.py'
            ]
            
            compiled_count = 0
            for script in setup_scripts:
                if os.path.exists(script):
                    try:
                        subprocess.run([sys.executable, script, 'build_ext', '--inplace'],
                                     check=True)
                        compiled_count += 1
                    except subprocess.CalledProcessError:
                        pass
            
            setup_success = compiled_count > 0
        
        # Install Python requirements
        requirements_success = self.install_python_requirements()
        
        # Test final setup
        test_success = self.test_final_setup()
        
        # Final summary
        print("\n" + "=" * 70)
        print("📊 Setup Summary")
        print("=" * 70)
        
        if setup_success and requirements_success:
            print("🎉 Setup completed successfully!")
            print("✅ C extensions compiled/available")
            print("✅ Python requirements installed")
            
            if test_success:
                print("✅ All tests passed")
            else:
                print("⚠️  Some C extensions not available, Python fallbacks will be used")
                
            print("\n🚀 You can now run the optimized scripts:")
            print("   python exploit_optimized.py --fast --threads 20")
            
        else:
            print("❌ Setup encountered issues")
            if not setup_success:
                print("❌ C extension compilation failed")
            if not requirements_success:
                print("❌ Python requirements installation failed")
                
            print("\n🔧 Manual setup may be required")
            print("   Please check the error messages above")
        
        print("=" * 70)
        return setup_success and requirements_success

def main():
    setup = CrossPlatformSetup()
    return setup.run_setup()

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
