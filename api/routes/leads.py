from fastapi import APIRouter, HTTPException, Depends
from utils.logger import get_logger
from utils.auth import verify_api_key, verify_n8n_webhook

log = get_logger("leads_api")
router = APIRouter(prefix="/leads", tags=["leads"])


def get_supabase():
    from tools.supabase_client import supabase
    return supabase


@router.get("/", dependencies=[Depends(verify_api_key)])
async def list_leads(campaign_id: str = None, tier: str = None, limit: int = 100):
    """List leads, optionally filtered by campaign or tier."""
    if limit > 1000:
        limit = 1000  # Hard cap to prevent abuse
    supabase = get_supabase()
    query = supabase.table("leads").select("*").order("score", desc=True).limit(limit)
    if campaign_id:
        query = query.eq("campaign_id", campaign_id)
    if tier:
        query = query.eq("tier", tier)
    result = query.execute()
    return result.data or []


@router.post("/mark-replied", dependencies=[Depends(verify_n8n_webhook)])
async def mark_replied(payload: dict):
    """
    Mark a lead as replied.
    Called by n8n Gmail trigger when a reply is detected.
    Payload: { "threadId": "...", "email": "..." }
    """
    supabase = get_supabase()
    thread_id = payload.get("threadId")

    if not thread_id:
        raise HTTPException(status_code=400, detail="threadId is required")

    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        supabase.table("messages").update({"replied_at": now}).eq("gmail_thread_id", thread_id).execute()

        msg_result = supabase.table("messages").select("lead_id").eq("gmail_thread_id", thread_id).execute()
        if msg_result.data:
            lead_id = msg_result.data[0]["lead_id"]
            supabase.table("leads").update({"status": "replied"}).eq("id", lead_id).execute()
            log.info(f"Lead {lead_id} marked as replied (thread: {thread_id})")

        return {"status": "updated", "thread_id": thread_id}
    except Exception as e:
        log.error(f"Failed to mark replied: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark replied")


@router.get("/due-followups", dependencies=[Depends(verify_n8n_webhook)])
async def get_due_followups():
    """
    Get messages that need follow-up.
    Called by n8n scheduler to find leads needing day-3 or day-7 follow-ups.
    """
    supabase = get_supabase()
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    day3_cutoff = (now - timedelta(days=3)).isoformat()
    day7_cutoff = (now - timedelta(days=7)).isoformat()

    day3 = supabase.table("messages").select(
        "*, leads(email, company_name, contact_name)"
    ).eq("sequence_step", 1).is_("replied_at", "null").lte("sent_at", day3_cutoff).execute()

    day7 = supabase.table("messages").select(
        "*, leads(email, company_name, contact_name)"
    ).eq("sequence_step", 2).is_("replied_at", "null").lte("sent_at", day7_cutoff).execute()

    return {
        "day3_followups": day3.data or [],
        "day7_followups": day7.data or [],
    }


@router.post("/send-followup", dependencies=[Depends(verify_n8n_webhook)])
async def send_followup(payload: dict):
    """Send a follow-up email for a specific message."""
    supabase = get_supabase()
    message_id = payload.get("message_id")
    step = payload.get("step", 2)

    if not message_id:
        raise HTTPException(status_code=400, detail="message_id is required")

    try:
        msg_result = supabase.table("messages").select(
            "*, leads(email, company_name, campaigns(sender_email, sender_name))"
        ).eq("id", message_id).execute()

        if not msg_result.data:
            raise HTTPException(status_code=404, detail="Message not found")

        msg = msg_result.data[0]
        lead_email = msg.get("leads", {}).get("email")
        follow_up_body = msg.get("follow_up_1") if step == 2 else msg.get("follow_up_2")
        sender_email = msg.get("leads", {}).get("campaigns", {}).get("sender_email")

        if not lead_email or not follow_up_body:
            return {"status": "skipped", "reason": "no_email_or_followup"}

        from tools.gmail import send_email
        from datetime import datetime, timezone

        subject = f"Re: {msg.get('subject', '')}"
        result = send_email(lead_email, subject, follow_up_body, sender_email)

        if result.get("success"):
            supabase.table("messages").insert({
                "lead_id": msg.get("lead_id"),
                "campaign_id": msg.get("campaign_id"),
                "subject": subject,
                "body": follow_up_body,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sequence_step": step,
                "gmail_thread_id": msg.get("gmail_thread_id"),
            }).execute()
            return {"status": "sent", "to": lead_email, "step": step}
        else:
            return {"status": "failed", "error": result.get("error")}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Follow-up send failed: {e}")
        raise HTTPException(status_code=500, detail="Follow-up send failed")


@router.get("/export", dependencies=[Depends(verify_api_key)])
async def export_leads_csv(campaign_id: str = None):
    """Export leads as CSV data for download."""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    supabase = get_supabase()
    query = supabase.table("leads").select(
        "company_name,domain,contact_name,contact_role,email,email_confidence,tier,score,status,industry,location,created_at"
    ).order("score", desc=True).limit(5000)

    if campaign_id:
        query = query.eq("campaign_id", campaign_id)

    result = query.execute()
    leads = result.data or []

    if not leads:
        raise HTTPException(status_code=404, detail="No leads found")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=leads[0].keys())
    writer.writeheader()
    writer.writerows(leads)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
    )
