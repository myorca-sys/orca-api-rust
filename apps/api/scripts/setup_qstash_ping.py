#!/usr/bin/env python3
"""
setup_qstash_ping.py

Registers cron jobs on Upstash QStash for background maintenance:
1. Healthz Keep-Alive (Every 4 minutes)
2. Aggregate Stats (Daily at midnight)
3. Active Provider Health Check (Every 15 minutes)
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

QSTASH_URL = "https://qstash.upstash.io/v2/schedules"
QSTASH_TOKEN = os.getenv("QSTASH_TOKEN") or os.getenv("UPSTASH_QSTASH_TOKEN")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

API_URL = "https://jonyyyyyyyu-anime-scraper-api.hf.space"

def register_cron(endpoint, cron_expression, method="GET", extra_headers=None):
    if not QSTASH_TOKEN:
        print("Error: QSTASH_TOKEN environment variable is not set.")
        return

    headers = {
        "Authorization": f"Bearer {QSTASH_TOKEN}",
        "Content-Type": "application/json",
        "Upstash-Cron": cron_expression,
        "Upstash-Method": method,
    }
    
    if extra_headers:
        for k, v in extra_headers.items():
            headers[f"Upstash-Forward-{k}"] = v

    full_url = f"{API_URL}{endpoint}"
    
    try:
        response = requests.post(
            f"{QSTASH_URL}/{full_url}",
            headers=headers
        )
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Success! Cron job registered for {endpoint}")
            print(f"Schedule ID: {data.get('scheduleId')}")
        else:
            print(f"Failed to register cron job for {endpoint}. Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error making request to QStash: {e}")

if __name__ == "__main__":
    print("Setting up QStash background jobs...")
    
    # 1. Keep-Alive Ping
    register_cron("/healthz", "*/4 * * * *", "GET")
    
    if not ADMIN_API_KEY:
        print("Warning: ADMIN_API_KEY not set. Cannot register admin cron jobs.")
    else:
        auth_headers = {"x-admin-key": ADMIN_API_KEY}
        
        # 2. Aggregate Stats (Daily at 00:00 UTC)
        register_cron("/api/v2/admin/cron/aggregate", "0 0 * * *", "POST", auth_headers)
        
        # 3. Active Provider Health Check (Every 15 minutes)
        register_cron("/api/v2/admin/cron/health-check", "*/15 * * * *", "POST", auth_headers)
    
    print("Done!")
