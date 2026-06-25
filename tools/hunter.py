import httpx
from config import settings
from utils.logger import get_logger
from utils.retry import with_retry

log = get_logger("hunter")


@with_retry(max_retries=3, delay=1.5)
async def find_email(domain: str, full_name: str = None) -> dict:
    """
    Find email address for a contact at a domain.
    Tries email-finder (name + domain) first, falls back to domain-search.
    Returns: {"email": str|None, "confidence": int}
    """
    if settings.hunter_api_key == "placeholder":
        log.debug(f"Hunter API key is placeholder — skipping {domain}")
        return {"email": None, "confidence": 0}

    async with httpx.AsyncClient(timeout=20) as client:
        # Try email finder if we have a name
        if full_name:
            parts = full_name.strip().split()
            first = parts[0] if parts else ""
            last = parts[-1] if len(parts) > 1 else ""

            try:
                resp = await client.get(
                    "https://api.hunter.io/v2/email-finder",
                    params={
                        "domain": domain,
                        "first_name": first,
                        "last_name": last,
                        "api_key": settings.hunter_api_key,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    if data.get("email"):
                        log.debug(f"Hunter email-finder: {data['email']} @ {domain}")
                        return {"email": data["email"], "confidence": data.get("score", 0)}
            except Exception as e:
                log.debug(f"Hunter email-finder failed for {domain}: {e}")

        # Fallback: domain search
        try:
            resp = await client.get(
                "https://api.hunter.io/v2/domain-search",
                params={
                    "domain": domain,
                    "api_key": settings.hunter_api_key,
                    "limit": 5,
                },
            )
            if resp.status_code == 200:
                emails = resp.json().get("data", {}).get("emails", [])
                if emails:
                    best = max(emails, key=lambda x: x.get("confidence", 0))
                    log.debug(f"Hunter domain-search found email for {domain}")
                    return {"email": best["value"], "confidence": best["confidence"]}
        except Exception as e:
            log.debug(f"Hunter domain-search failed for {domain}: {e}")

    log.debug(f"Hunter found no email for {domain}")
    return {"email": None, "confidence": 0}
