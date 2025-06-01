#!/usr/bin/env python3
"""
IoT Security Research - C2 Server Runner (Fixed)
Educational Purpose Only - For Controlled Lab Environment
"""

import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('c2_server.log')
    ]
)

# Import and run the server
try:
    # Import local modules directly
    from c2_server import app
    
    # Run the app
    if __name__ == '__main__':
        print("\n===================================================")
        print("Starting C2 server on port 5000...")
        print("===================================================\n")
        app.run(host='0.0.0.0', port=5000, debug=True)
        
except Exception as e:
    logging.error(f"Error starting C2 server: {e}")
    print(f"Error: {e}")
    sys.exit(1)