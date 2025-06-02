import sqlite3
import os

print("Current directory:", os.getcwd())
print("Checking if database file exists:", os.path.exists('c2_server.db'))

try:
    conn = sqlite3.connect('c2_server.db')
    cursor = conn.cursor()
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("Tables in database:")
    for table in tables:
        print(f"- {table[0]}")
        
        # Show table structure
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        print(f"  Columns in {table[0]}:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # Show some sample data
        cursor.execute(f"SELECT * FROM {table[0]} LIMIT 5")
        rows = cursor.fetchall()
        if rows:
            print(f"  Sample data from {table[0]} (up to 5 rows):")
            for row in rows:
                print(f"  - {row}")
        else:
            print(f"  No data in {table[0]}")
        
        print()
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
