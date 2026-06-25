import asyncio
import random
from datetime import datetime, timezone
from typing import Optional

from tools.gmail import send_email, get_gmail_service
from config import settings
from utils.logger import get_logger

log = get_logger("outreach")


def get_daily_send_count(campaign_id: str) -> int:
    """Get number of emails sent today for this campaign."""
    try:
        from tools.supabase_client import supabase
        today = datetime.now(timezone.utc).date().isoformat()
        result = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("campaign_id", campaign_id)
            .gte("sent_at", today)
            .execute()
        )
        return result.count or 0
    except Exception as e:
        log.warning(f"Could not get daily send count: {e}")
        return 0


async def send_single_email(lead: dict, campaign: dict) -> dict:
    """Send initial outreach email to one lead and save to DB."""
    messages = lead.get("outreach_messages", {})

    if not lead.get("email"):
        lead["status"] = "skipped_no_email"
        log.debug(f"Skipped {lead.get('company_name')} — no email")
        return lead

    if not messages.get("subject") or not messages.get("body"):
        lead["status"] = "skipped_no_message"
        return lead

    # A/B test: randomly pick subject variant
    subject = messages.get("subject_b") if (random.random() < 0.5 and messages.get("subject_b")) else messages["subject"]
    ab_variant = "B" if subject == messages.get("subject_b") else "A"

    result = send_email(
        to=lead["email"],
        subject=subject,
        body=messages["body"],
        sender=campaign["sender_email"],
    )

    if result.get("success"):
        lead["status"] = "sent"
        lead["gmail_message_id"] = result.get("message_id")
        lead["gmail_thread_id"] = result.get("thread_id")
        lead["sent_at"] = datetime.now(timezone.utc).isoformat()
        lead["ab_variant"] = ab_variant

        # Save to database
        try:
            from tools.supabase_client import supabase
            supabase.table("messages").insert({
                "lead_id": lead.get("id"),
                "campaign_id": campaign.get("id"),
                "subject": subject,
                "body": messages["body"],
                "follow_up_1": messages.get("follow_up_1"),
                "follow_up_2": messages.get("follow_up_2"),
                "sent_at": lead["sent_at"],
                "sequence_step": 1,
                "ab_variant": ab_variant,
                "gmail_message_id": result.get("message_id"),
                "gmail_thread_id": result.get("thread_id"),
            }).execute()
        except Exception as e:
            log.warning(f"DB save failed for {lead.get('company_name')}: {e}")

        log.info(f"[Outreach] ✓ Sent to {lead['email']} | {lead.get('company_name')} | Subject variant {ab_variant}")
    else:
        lead["status"] = "send_failed"
        lead["error"] = result.get("error")
        log.warning(f"[Outreach] ✗ Failed to send to {lead['email']}: {result.get('error')}")

    # Human-simulation delay: 30-90 seconds between sends
    delay = random.uniform(30, 90)
    log.debug(f"[Outreach] Waiting {delay:.0f}s before next send...")
    await asyncio.sleep(delay)

    return lead


async def outreach_agent(state: dict) -> dict:
    """
    Agent 5: Send emails to all ready leads, respecting daily limits.
    Enforces 50 emails/day limit and human-like delays.
    """
    campaign = state["campaign"]
    queue = state.get("outreach_queue", [])

    # Check daily limit
    daily_sent = get_daily_send_count(campaign.get("id", "unknown"))
    remaining = max(0, settings.daily_email_limit - daily_sent)

    ready = [l for l in queue if l.get("status") == "ready_to_send"]
    to_send = ready[:remaining]

    log.info(f"[Outreach] Daily limit: {settings.daily_email_limit} | Sent today: {daily_sent} | Sending now: {len(to_send)}")

    if not to_send:
        log.info("[Outreach] Daily limit reached or no leads ready. Skipping.")
        state["sent_messages"] = []
        return state

    results = []
    for lead in to_send:
        result = await send_single_email(lead, campaign)
        results.append(result)

    sent = sum(1 for r in results if r.get("status") == "sent")
    failed = sum(1 for r in results if r.get("status") == "send_failed")
    log.info(f"[Outreach] Complete — Sent: {sent} | Failed: {failed}")

    state["sent_messages"] = results
    return state
