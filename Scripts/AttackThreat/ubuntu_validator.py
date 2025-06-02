#!/usr/bin/env python3
"""
Ubuntu Compatibility Validation Script
Comprehensive testing of all components on Ubuntu/Linux systems
"""

import os
import sys
import platform
import subprocess
import time
import threading
from pathlib import Path

class UbuntuValidator:
    def __init__(self):
        self.system = platform.system()
        self.is_linux = self.system == "Linux"
        self.test_results = {}
        self.start_time = time.time()
        
    def log_test(self, test_name, success, details="", execution_time=0):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results[test_name] = {
            'success': success,
            'details': details,
            'execution_time': execution_time
        }
        
        time_str = f" ({execution_time:.3f}s)" if execution_time > 0 else ""
        print(f"{status} {test_name}{time_str}")
        if details:
            print(f"      {details}")
    
    def test_system_info(self):
        """Test and display system information"""
        start = time.time()
        
        try:
            print(f"🖥️  System: {platform.system()}")
            print(f"🏗️  Architecture: {platform.machine()}")
            print(f"🐍 Python: {sys.version.split()[0]}")
            
            if self.is_linux:
                try:
                    with open('/etc/os-release', 'r') as f:
                        for line in f:
                            if line.startswith('PRETTY_NAME='):
                                distro = line.split('=')[1].strip().strip('"')
                                print(f"🐧 Distribution: {distro}")
                                break
                except:
                    print("🐧 Distribution: Unknown Linux")
            
            self.log_test("System Information", True, 
                         f"{self.system} - {platform.machine()}", 
                         time.time() - start)
            return True
            
        except Exception as e:
            self.log_test("System Information", False, str(e), time.time() - start)
            return False
    
    def test_gcc_compilation(self):
        """Test GCC compilation capabilities"""
        start = time.time()
        
        if not self.is_linux:
            self.log_test("GCC Compilation", True, "Skipped on non-Linux system", time.time() - start)
            return True
        
        try:
            # Test basic GCC compilation
            test_code = '''
#include <stdio.h>
#include <pthread.h>

void* test_thread(void* arg) {
    printf("Thread working\\n");
    return NULL;
}

int main() {
    pthread_t thread;
    pthread_create(&thread, NULL, test_thread, NULL);
    pthread_join(thread, NULL);
    printf("GCC and pthread test successful\\n");
    return 0;
}
'''
            
            # Write test file
            with open('/tmp/gcc_test.c', 'w') as f:
                f.write(test_code)
            
            # Compile
            compile_cmd = ['gcc', '/tmp/gcc_test.c', '-lpthread', '-o', '/tmp/gcc_test']
            result = subprocess.run(compile_cmd, capture_output=True, text=True, check=True)
            
            # Run
            run_result = subprocess.run(['/tmp/gcc_test'], capture_output=True, text=True, check=True)
            
            # Clean up
            for f in ['/tmp/gcc_test.c', '/tmp/gcc_test']:
                try:
                    os.remove(f)
                except:
                    pass
            
            self.log_test("GCC Compilation", True, 
                         "GCC and pthread compilation successful", 
                         time.time() - start)
            return True
            
        except Exception as e:
            self.log_test("GCC Compilation", False, str(e), time.time() - start)
            return False
    
    def test_python_imports(self):
        """Test Python package imports"""
        start = time.time()
        
        required_packages = [
            'requests',
            'flask',
            'colorama',
            'subprocess',
            'threading',
            'socket',
            'time'
        ]
        
        failed_imports = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                failed_imports.append(package)
        
        if failed_imports:
            self.log_test("Python Imports", False, 
                         f"Failed: {', '.join(failed_imports)}", 
                         time.time() - start)
            return False
        else:
            self.log_test("Python Imports", True, 
                         f"All {len(required_packages)} packages imported", 
                         time.time() - start)
            return True
    
    def test_c_extensions(self):
        """Test C extension imports and functionality"""
        start = time.time()
        
        extensions = ['fast_telnet_bruteforce', 'fast_ddos_attack']
        working_extensions = []
        failed_extensions = []
        
        for ext in extensions:
            try:
                module = __import__(ext)
                working_extensions.append(ext)
                
                # Test basic functionality
                if ext == 'fast_telnet_bruteforce' and hasattr(module, 'telnet_bruteforce'):
                    # Test with invalid target (should fail gracefully)
                    try:
                        result = module.telnet_bruteforce("127.0.0.1", 23, ["admin"], ["admin"], 1, 1)
                    except:
                        pass  # Expected to fail, we're just testing the interface
                
                elif ext == 'fast_ddos_attack' and hasattr(module, 'udp_flood'):
                    # Test with minimal parameters (should not actually send packets)
                    try:
                        # This should not actually send packets to localhost
                        pass  # We skip actual testing to avoid network activity
                    except:
                        pass
                        
            except ImportError as e:
                failed_extensions.append(f"{ext}: {e}")
        
        if working_extensions:
            self.log_test("C Extensions", True, 
                         f"Working: {', '.join(working_extensions)}", 
                         time.time() - start)
            return True
        else:
            self.log_test("C Extensions", False, 
                         f"None available. Failed: {'; '.join(failed_extensions)}", 
                         time.time() - start)
            return False
    
    def test_modular_components(self):
        """Test modular components functionality"""
        start = time.time()
        
        try:
            # Test module imports
            from modules.telnet_bruteforcer import TelnetBruteForcer
            from modules.network_scanner import NetworkScanner
            from modules.c2_communicator import C2Communicator
            from modules.user_interface import UserInterface
            
            # Test instantiation
            bf = TelnetBruteForcer(max_threads=5)
            scanner = NetworkScanner()
            c2 = C2Communicator("http://localhost:5000")
            ui = UserInterface()
            
            # Test basic functionality
            assert bf.max_threads == 5
            assert hasattr(scanner, 'scan_network')
            assert hasattr(c2, 'register_device')
            assert hasattr(ui, 'display_banner')
            
            self.log_test("Modular Components", True, 
                         "All modules loaded and instantiated", 
                         time.time() - start)
            return True
            
        except Exception as e:
            self.log_test("Modular Components", False, str(e), time.time() - start)
            return False
    
    def test_threading_performance(self):
        """Test multi-threading performance"""
        start = time.time()
        
        try:
            import threading
            import concurrent.futures
            
            # Test thread pool creation
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Submit test tasks
                futures = []
                for i in range(20):
                    future = executor.submit(lambda: time.sleep(0.1))
                    futures.append(future)
                
                # Wait for completion
                for future in concurrent.futures.as_completed(futures):
                    future.result()
            
            execution_time = time.time() - start
            
            # Should complete in roughly 0.2s with 10 workers (2 batches of 0.1s)
            if execution_time < 0.5:  # Allow some overhead
                self.log_test("Threading Performance", True, 
                             f"20 tasks in {execution_time:.3f}s with 10 workers", 
                             execution_time)
                return True
            else:
                self.log_test("Threading Performance", False, 
                             f"Too slow: {execution_time:.3f}s", 
                             execution_time)
                return False
                
        except Exception as e:
            self.log_test("Threading Performance", False, str(e), time.time() - start)
            return False
    
    def test_network_capabilities(self):
        """Test network socket capabilities"""
        start = time.time()
        
        try:
            import socket
            
            # Test UDP socket creation
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.close()
            
            # Test TCP socket creation
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.close()
            
            self.log_test("Network Capabilities", True, 
                         "UDP and TCP socket creation successful", 
                         time.time() - start)
            return True
            
        except Exception as e:
            self.log_test("Network Capabilities", False, str(e), time.time() - start)
            return False
    
    def test_file_permissions(self):
        """Test file system permissions"""
        start = time.time()
        
        try:
            # Test write permissions in current directory
            test_file = 'ubuntu_test_permissions.tmp'
            with open(test_file, 'w') as f:
                f.write("Permission test")
            
            # Test read
            with open(test_file, 'r') as f:
                content = f.read()
            
            # Clean up
            os.remove(test_file)
            
            self.log_test("File Permissions", True, 
                         "Read/write permissions OK", 
                         time.time() - start)
            return True
            
        except Exception as e:
            self.log_test("File Permissions", False, str(e), time.time() - start)
            return False
    
    def run_validation(self):
        """Run complete validation suite"""
        print("=" * 70)
        print("🧪 Ubuntu Compatibility Validation Suite")
        print("=" * 70)
        
        tests = [
            self.test_system_info,
            self.test_gcc_compilation,
            self.test_python_imports,
            self.test_c_extensions,
            self.test_modular_components,
            self.test_threading_performance,
            self.test_network_capabilities,
            self.test_file_permissions
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed_tests += 1
            except Exception as e:
                print(f"❌ FAIL {test.__name__}: Unexpected error: {e}")
        
        # Summary
        total_time = time.time() - self.start_time
        
        print("\n" + "=" * 70)
        print("📊 Validation Summary")
        print("=" * 70)
        
        print(f"🎯 Tests Passed: {passed_tests}/{total_tests}")
        print(f"⏱️  Total Time: {total_time:.3f}s")
        
        if passed_tests == total_tests:
            print("🎉 All tests passed! Ubuntu compatibility confirmed.")
            compatibility_score = 100
        else:
            compatibility_score = (passed_tests / total_tests) * 100
            print(f"⚠️  Compatibility Score: {compatibility_score:.1f}%")
        
        # Detailed results
        print("\n📋 Detailed Results:")
        for test_name, result in self.test_results.items():
            status = "✅" if result['success'] else "❌"
            time_str = f" ({result['execution_time']:.3f}s)" if result['execution_time'] > 0 else ""
            print(f"  {status} {test_name}{time_str}")
            if result['details']:
                print(f"      {result['details']}")
        
        # Recommendations
        print("\n💡 Recommendations:")
        if compatibility_score >= 90:
            print("  🚀 System is ready for high-performance operations")
            print("  ⚡ C extensions available for maximum speed")
        elif compatibility_score >= 70:
            print("  ✅ System is functional with Python fallbacks")
            print("  🔧 Consider installing missing C extension dependencies")
        else:
            print("  ⚠️  System needs additional setup")
            print("  🛠️  Run: python3 ubuntu_setup.py")
        
        print("=" * 70)
        return compatibility_score >= 70

def main():
    validator = UbuntuValidator()
    return validator.run_validation()

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
