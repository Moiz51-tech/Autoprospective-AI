from datetime import datetime, timezone
from utils.logger import get_logger

log = get_logger("analytics")


async def analytics_agent(state: dict) -> dict:
    """
    Agent 6: Track performance, save all leads to DB, feed learning patterns.
    Always runs — even when no emails were sent (cold-only runs).
    """
    campaign = state.get("campaign", {})
    campaign_id = campaign.get("id", "unknown")

    scored_leads = state.get("scored_leads", [])
    sent_messages = state.get("sent_messages", [])
    errors = state.get("errors", [])

    # ── Compute run stats ────────────────────────────────
    raw_count = len(state.get("raw_leads", []))
    enriched_count = len(state.get("enriched_leads", []))
    hot_count = sum(1 for l in scored_leads if l.get("tier") == "hot")
    warm_count = sum(1 for l in scored_leads if l.get("tier") == "warm")
    cold_count = sum(1 for l in scored_leads if l.get("tier") == "cold")
    sent_count = sum(1 for m in sent_messages if m.get("status") == "sent")
    failed_count = sum(1 for m in sent_messages if m.get("status") == "send_failed")
    skipped_count = sum(1 for m in sent_messages if m.get("status", "").startswith("skipped"))

    stats = {
        "campaign_id": campaign_id,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "raw_leads": raw_count,
        "enriched_leads": enriched_count,
        "hot_leads": hot_count,
        "warm_leads": warm_count,
        "cold_leads": cold_count,
        "emails_sent": sent_count,
        "emails_failed": failed_count,
        "emails_skipped": skipped_count,
        "errors": errors,
    }

    log.info(
        f"[Analytics] Run complete for {campaign_id}:\n"
        f"  Raw: {raw_count} → Enriched: {enriched_count} → "
        f"Hot: {hot_count} | Warm: {warm_count} | Cold: {cold_count}\n"
        f"  Sent: {sent_count} | Failed: {failed_count} | Skipped: {skipped_count} | Errors: {len(errors)}"
    )

    # ── Persist to database ──────────────────────────────
    try:
        from tools.supabase_client import supabase

        # 1. Save campaign run record
        supabase.table("campaign_runs").insert(stats).execute()

        # 2. Upsert ALL scored leads (including cold — data is valuable)
        if scored_leads:
            leads_to_save = []
            for lead in scored_leads:
                leads_to_save.append({
                    "campaign_id": campaign_id,
                    "company_name": lead.get("company_name"),
                    "domain": lead.get("domain"),
                    "contact_name": lead.get("contact_name"),
                    "contact_role": lead.get("contact_role"),
                    "email": lead.get("email"),
                    "email_confidence": lead.get("email_confidence", 0),
                    "linkedin_url": lead.get("linkedin_url"),
                    "company_summary": lead.get("company_summary"),
                    "score": lead.get("score", 0),
                    "tier": lead.get("tier", "unscored"),
                    "score_reasons": lead.get("score_reasons", []),
                    "llm_reasoning": lead.get("llm_reasoning"),
                    "status": lead.get("status", "new"),
                    "source": lead.get("source", "apollo"),
                    "employees": lead.get("employees"),
                    "industry": lead.get("industry"),
                    "location": lead.get("location"),
                })
            # Upsert by domain — prevents duplicate leads across campaign runs
            supabase.table("leads").upsert(leads_to_save, on_conflict="domain").execute()
            log.info(f"[Analytics] Upserted {len(leads_to_save)} leads to DB")

        # 3. Save learning patterns from hot leads
        if hot_count > 0:
            hot_leads = [l for l in scored_leads if l.get("tier") == "hot"]
            for lead in hot_leads[:10]:
                for reason in lead.get("score_reasons", []):
                    try:
                        supabase.table("learning_patterns").upsert({
                            "pattern_type": "icp_attribute",
                            "value": reason,
                            "campaign_id": campaign_id,
                        }, on_conflict="pattern_type,value,campaign_id").execute()
                    except Exception:
                        pass  # Non-critical

    except Exception as e:
        log.warning(f"[Analytics] DB save failed (non-fatal): {e}")

    state["run_stats"] = stats
    return state
