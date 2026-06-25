import base64
import os
from email.mime.text import MIMEText
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings
from utils.logger import get_logger

log = get_logger("gmail")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

_gmail_service = None


def get_gmail_service():
    """
    Authenticate and return Gmail API service.
    Uses token.json if present, otherwise prompts OAuth flow.
    """
    global _gmail_service
    if _gmail_service:
        return _gmail_service

    creds = None

    if os.path.exists(settings.gmail_token_path):
        creds = Credentials.from_authorized_user_file(settings.gmail_token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                log.info("Gmail token refreshed")
            except Exception as e:
                log.warning(f"Token refresh failed: {e} — re-authenticating")
                creds = None

        if not creds:
            if not os.path.exists(settings.gmail_credentials_path):
                raise FileNotFoundError(
                    f"Gmail credentials not found at '{settings.gmail_credentials_path}'. "
                    "Run: python scripts/setup_gmail.py"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.gmail_credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(settings.gmail_token_path, "w") as token:
            token.write(creds.to_json())
        log.info("Gmail token saved")

    _gmail_service = build("gmail", "v1", credentials=creds)
    return _gmail_service


def create_message(to: str, subject: str, body: str, sender: str, thread_id: Optional[str] = None) -> dict:
    """Create a Gmail API message object."""
    msg = MIMEText(body, "plain")
    msg["to"] = to
    msg["from"] = sender
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = {"raw": raw}
    if thread_id:
        result["threadId"] = thread_id
    return result


def send_email(to: str, subject: str, body: str, sender: str, thread_id: Optional[str] = None) -> dict:
    """
    Send an email via Gmail API.
    Returns: {"success": bool, "message_id": str, "thread_id": str, "error": str}
    """
    try:
        service = get_gmail_service()
        msg = create_message(to, subject, body, sender, thread_id)
        result = service.users().messages().send(userId="me", body=msg).execute()
        log.info(f"Email sent to {to} | MsgID: {result['id']}")
        return {
            "success": True,
            "message_id": result["id"],
            "thread_id": result.get("threadId"),
        }
    except FileNotFoundError as e:
        log.error(f"Gmail credentials missing: {e}")
        return {"success": False, "error": "Gmail not configured. Run scripts/setup_gmail.py"}
    except HttpError as e:
        log.error(f"Gmail API error sending to {to}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        log.error(f"Unexpected error sending to {to}: {e}")
        return {"success": False, "error": str(e)}


def get_recent_replies(since_hours: int = 24) -> list:
    """Fetch recent replies in the inbox."""
    try:
        service = get_gmail_service()
        results = service.users().messages().list(
            userId="me",
            q=f"in:inbox newer_than:{since_hours}h",
            maxResults=50,
        ).execute()
        messages = results.get("messages", [])
        log.info(f"Found {len(messages)} recent inbox messages")
        return messages
    except Exception as e:
        log.error(f"Failed to fetch replies: {e}")
        return []
