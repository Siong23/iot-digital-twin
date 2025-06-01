#!/usr/bin/env python3
"""
IoT Digital Twin - Test Suite Runner

Comprehensive test runner for the registration verification system.
Executes all test scenarios and provides a summary report.

Educational Purpose Only - For Controlled Lab Environment
Author: IoT Security Research Team
Date: June 2025
"""

import subprocess
import sys
import os
from datetime import datetime

def run_test(test_file, description):
    """Run a single test and return the result"""
    print(f"\n{'='*60}")
    print(f"🧪 Running: {description}")
    print(f"📝 File: {test_file}")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, 
                              text=True, 
                              timeout=120)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
            
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Test timed out after 120 seconds")
        return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

def main():
    """Run all registration verification tests"""
    print("🚀 IoT Digital Twin - Registration Verification Test Suite")
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Change to the correct directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    tests = [
        ("test_registration_verification.py", "Basic Registration Verification"),
        ("test_registration_fix.py", "Enhanced Registration Fix Testing"),
        ("test_ddos_comprehensive.py", "Comprehensive DDoS Attack Analysis")
    ]
    
    results = []
    
    for test_file, description in tests:
        if os.path.exists(test_file):
            success = run_test(test_file, description)
            results.append((test_file, description, success))
        else:
            print(f"⚠️  Test file not found: {test_file}")
            results.append((test_file, description, False))
    
    # Print summary
    print("\n" + "="*80)
    print("📊 TEST SUITE SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, _, success in results if success)
    total = len(results)
    
    for test_file, description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {description}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Registration verification system is working correctly!")
        return 0
    else:
        print("⚠️  Some tests failed - Check the output above for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())
