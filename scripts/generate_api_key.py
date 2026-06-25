#!/usr/bin/env python3
"""
Generate secure random keys for API_SECRET_KEY and N8N_WEBHOOK_SECRET.
Run once during setup: python scripts/generate_api_key.py
"""
import secrets

api_key = secrets.token_hex(32)
webhook_secret = secrets.token_hex(24)

print("=" * 60)
print("Add these to your .env file:")
print("=" * 60)
print(f"API_SECRET_KEY={api_key}")
print(f"N8N_WEBHOOK_SECRET={webhook_secret}")
print("=" * 60)
print("\nAlso set these as environment variables in Railway and n8n.")
