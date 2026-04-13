#!/usr/bin/env python3
"""
Ping script to keep Render service awake.
Run this on a separate always-on server (like a Raspberry Pi, VPS, or cron-job.org)
Usage: python ping.py https://your-app.onrender.com
"""

import requests
import time
import sys
import os
from datetime import datetime

def ping_service(url):
    """Ping the /check endpoint and print status"""
    try:
        response = requests.get(f"{url}/check", timeout=10)
        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Service is awake")
            return True
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Service returned {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Ping failed: {e}")
        return False

def main():
    # Get URL from command line or environment variable
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = os.environ.get('RENDER_EXTERNAL_URL')
        if not url:
            print("Error: Please provide service URL as argument or set RENDER_EXTERNAL_URL")
            print("Usage: python ping.py https://your-app.onrender.com")
            sys.exit(1)
    
    # Remove trailing slash if present
    url = url.rstrip('/')
    
    print(f"Starting ping service for {url}")
    print("Pinging every 5 minutes. Press Ctrl+C to stop.\n")
    
    while True:
        ping_service(url)
        time.sleep(300)  # 5 minutes

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nPing service stopped.")
        sys.exit(0)
      
