#!/usr/bin/env python3
"""
Run once to authenticate Gmail API.
Usage: python scripts/setup_gmail.py
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.gmail import get_gmail_service

if __name__ == "__main__":
    print("Setting up Gmail authentication...")
    try:
        service = get_gmail_service()
        profile = service.users().getProfile(userId="me").execute()
        print(f"Gmail authenticated: {profile.get('emailAddress')}")
        print("token.json saved to project root")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nSteps:\n1. Go to https://console.cloud.google.com/\n2. Enable Gmail API\n3. Create OAuth 2.0 Desktop credentials\n4. Download as credentials.json into project root")
        sys.exit(1)
