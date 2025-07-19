#!/usr/bin/env python3

"""
Startup script for Euro AIP Airport Explorer Web Application
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    print("🚁 Euro AIP Airport Explorer")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("server").exists():
        print("❌ Error: Please run this script from the 'web' directory")
        print("   Current directory:", os.getcwd())
        print("   Expected structure: web/server/main.py")
        sys.exit(1)
    
    # Check if airports.db exists
    db_path = os.getenv("AIRPORTS_DB", "airports.db")
    if not Path(db_path).exists():
        print(f"⚠️  Warning: Database file '{db_path}' not found")
        print("   You can set the AIRPORTS_DB environment variable to specify the path")
        print("   Example: export AIRPORTS_DB=/path/to/your/airports.db")
        
        # Check if there's an airports.db in the parent directory
        parent_db = Path("../airports.db")
        if parent_db.exists():
            print(f"   Found airports.db in parent directory: {parent_db.absolute()}")
            print(f"   Setting AIRPORTS_DB={parent_db.absolute()}")
            os.environ["AIRPORTS_DB"] = str(parent_db.absolute())
        else:
            print("   Please ensure airports.db exists and is accessible")
            response = input("   Continue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(1)
    
    # Check if requirements are installed
    try:
        import fastapi
        import uvicorn
        print("✅ Dependencies are installed")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Please install requirements:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    
    # Start the server
    print("\n🚀 Starting FastAPI server...")
    print("   Server will be available at: http://localhost:8000")
    print("   API documentation at: http://localhost:8000/docs")
    print("   Press Ctrl+C to stop the server")
    print("-" * 40)
    
    try:
        # Change to server directory and start
        os.chdir("server")
        subprocess.run([
            sys.executable, "main.py"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Server failed to start: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 