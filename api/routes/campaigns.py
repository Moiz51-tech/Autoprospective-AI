import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from models.schemas import CampaignCreate, CampaignResponse, CampaignRunResult
from agents.graph import run_campaign
from utils.logger import get_logger
from utils.auth import verify_api_key, verify_n8n_webhook

log = get_logger("campaigns_api")
router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def get_supabase():
    from tools.supabase_client import supabase
    return supabase


@router.post("/create", response_model=CampaignResponse, dependencies=[Depends(verify_api_key)])
async def create_campaign(campaign_data: CampaignCreate):
    """Create a new campaign in the database."""
    supabase = get_supabase()
    campaign_id = str(uuid.uuid4())

    try:
        supabase.table("campaigns").insert({
            "id": campaign_id,
            "name": campaign_data.name,
            "icp": campaign_data.icp.model_dump(),
            "sender_name": campaign_data.sender_name,
            "sender_company": campaign_data.sender_company,
            "sender_email": campaign_data.sender_email,
            "value_proposition": campaign_data.value_proposition,
            "social_proof": campaign_data.social_proof,
            "tone": campaign_data.tone,
            "status": "active",
        }).execute()

        return CampaignResponse(
            id=campaign_id,
            name=campaign_data.name,
            status="active",
            created_at=datetime.now(timezone.utc),
            icp=campaign_data.icp.model_dump(),
        )
    except Exception as e:
        log.error(f"Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail="Failed to create campaign")


@router.post("/{campaign_id}/run", dependencies=[Depends(verify_api_key)])
async def run_campaign_now(campaign_id: str, background_tasks: BackgroundTasks):
    """Trigger an immediate campaign run (async background task)."""
    supabase = get_supabase()

    try:
        result = supabase.table("campaigns").select("*").eq("id", campaign_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        campaign = result.data[0]
        if campaign.get("status") != "active":
            raise HTTPException(status_code=400, detail=f"Campaign is {campaign.get('status')}, not active")

        background_tasks.add_task(run_campaign, campaign)
        return {"status": "started", "campaign_id": campaign_id, "message": "Campaign run started in background"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to start campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start campaign")


@router.post("/run-scheduled", dependencies=[Depends(verify_n8n_webhook)])
async def run_scheduled_campaigns(background_tasks: BackgroundTasks):
    """Called by n8n cron trigger — runs all active campaigns."""
    supabase = get_supabase()

    try:
        result = supabase.table("campaigns").select("*").eq("status", "active").execute()
        campaigns = result.data or []
        log.info(f"Running {len(campaigns)} scheduled campaigns")

        for campaign in campaigns:
            background_tasks.add_task(run_campaign, campaign)

        return {"status": "ok", "ran": len(campaigns)}
    except Exception as e:
        log.error(f"Scheduled run failed: {e}")
        raise HTTPException(status_code=500, detail="Scheduled run failed")


@router.get("/", response_model=list, dependencies=[Depends(verify_api_key)])
async def list_campaigns():
    """List all campaigns."""
    supabase = get_supabase()
    result = supabase.table("campaigns").select("*").order("created_at", desc=True).execute()
    return result.data or []


@router.get("/{campaign_id}/stats", dependencies=[Depends(verify_api_key)])
async def get_campaign_stats(campaign_id: str):
    """Get stats for a specific campaign."""
    supabase = get_supabase()

    campaign_result = supabase.table("campaigns").select("*").eq("id", campaign_id).execute()
    if not campaign_result.data:
        raise HTTPException(status_code=404, detail="Campaign not found")

    runs = supabase.table("campaign_runs").select("*").eq("campaign_id", campaign_id).order("run_at", desc=True).limit(10).execute()
    leads_result = supabase.table("leads").select("tier,status").eq("campaign_id", campaign_id).execute()
    messages = supabase.table("messages").select("sent_at,opened_at,replied_at,ab_variant").eq("campaign_id", campaign_id).execute()

    leads_data = leads_result.data or []
    msgs = messages.data or []

    total_sent = sum(1 for m in msgs if m.get("sent_at"))
    total_replied = sum(1 for m in msgs if m.get("replied_at"))

    return {
        "campaign_id": campaign_id,
        "campaign": campaign_result.data[0],
        "runs": runs.data or [],
        "leads": {
            "total": len(leads_data),
            "hot": sum(1 for l in leads_data if l.get("tier") == "hot"),
            "warm": sum(1 for l in leads_data if l.get("tier") == "warm"),
            "cold": sum(1 for l in leads_data if l.get("tier") == "cold"),
        },
        "messages": {
            "sent": total_sent,
            "replied": total_replied,
            "reply_rate": f"{(total_replied / max(total_sent, 1) * 100):.1f}%",
            "ab_a": sum(1 for m in msgs if m.get("ab_variant") == "A"),
            "ab_b": sum(1 for m in msgs if m.get("ab_variant") == "B"),
        },
    }


@router.put("/{campaign_id}/pause", dependencies=[Depends(verify_api_key)])
async def pause_campaign(campaign_id: str):
    """Pause an active campaign."""
    supabase = get_supabase()
    result = supabase.table("campaigns").update({"status": "paused"}).eq("id", campaign_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"status": "paused", "campaign_id": campaign_id}


@router.put("/{campaign_id}/resume", dependencies=[Depends(verify_api_key)])
async def resume_campaign(campaign_id: str):
    """Resume a paused campaign."""
    supabase = get_supabase()
    result = supabase.table("campaigns").update({"status": "active"}).eq("id", campaign_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"status": "active", "campaign_id": campaign_id}
