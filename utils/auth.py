"""
API Key authentication for n8n webhooks and external callers.
"""
from fastapi import HTTPException, Security, Header
from fastapi.security import APIKeyHeader
from typing import Optional
from config import settings
from utils.logger import get_logger

log = get_logger("auth")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(x_api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Verify API key from X-API-Key header.
    Used to protect endpoints called by n8n and other automation tools.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if x_api_key != settings.api_secret_key:
        log.warning(f"Invalid API key attempt")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )
    return x_api_key


async def verify_n8n_webhook(x_webhook_secret: Optional[str] = Header(None)) -> str:
    """
    Verify n8n webhook secret for inbound webhook calls.
    Set X-Webhook-Secret header in your n8n HTTP Request nodes.
    """
    if not x_webhook_secret:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret header")
    if x_webhook_secret != settings.n8n_webhook_secret:
        log.warning("Invalid n8n webhook secret")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    return x_webhook_secret
