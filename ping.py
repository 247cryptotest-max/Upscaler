#!/usr/bin/env python3
"""
Ping script to keep Render service awake (run externally, e.g., on a cron job or a separate always-on machine).
Pings the service every 5 minutes.
Replace the URL with your actual Render service URL.
"""
import requests
import time
import sys

# ⚠️ CHANGE THIS TO YOUR ACTUAL RENDER URL ⚠️
RENDER_URL = "https://upscaler-tg2b.onrender.com"

def ping_service():
    try:
        resp = requests.get(RENDER_URL, timeout=10)
        if resp.status_code == 200:
            print(f"[{time.ctime()}] Ping successful: {resp.status_code}")
        else:
            print(f"[{time.ctime()}] Ping returned {resp.status_code}")
    except Exception as e:
        print(f"[{time.ctime()}] Ping failed: {e}")

if __name__ == "__main__":
    print("Starting keep-awake pinger every 5 minutes. Press Ctrl+C to stop.")
    while True:
        ping_service()
        time.sleep(300)  # 5 minutes
