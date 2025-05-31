# Simple runner script for the C2 server
import os
import sys

# Add the parent directory to sys.path if run directly
if __name__ == "__main__":
    print("Starting C2 server...")
    # Get the parent directory
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Add to path if not already there
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Import the app from the module
    from c2_server.c2_server import app
    app.run(host='0.0.0.0', port=5000, debug=False)
