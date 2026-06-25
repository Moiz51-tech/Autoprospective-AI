import asyncio
from tools.apollo import find_contacts_at_company
from tools.scraper import search_google_maps, extract_domain
from tools.csv_leads import load_leads_from_csv
from config import settings
from utils.logger import get_logger
import os

log = get_logger("lead_finder")


def normalize_leads(leads: list) -> list:
    """Standardize lead format across all sources."""
    normalized = []
    seen_domains = set()

    for lead in leads:
        raw_domain = (
            lead.get("primary_domain")
            or lead.get("website_url")
            or lead.get("website")
            or lead.get("domain")
            or ""
        )
        domain = extract_domain(raw_domain) if "." in raw_domain else raw_domain

        if not domain or domain in seen_domains:
            continue

        seen_domains.add(domain)
        normalized.append({
            "company_name": lead.get("name") or lead.get("company_name", "Unknown"),
            "domain": domain,
            "employees": lead.get("num_employees") or lead.get("employees") or 0,
            "industry": lead.get("industry", ""),
            "location": lead.get("city") or lead.get("location", ""),
            "linkedin_url": lead.get("linkedin_url", ""),
            "source": lead.get("source", "csv"),
            "raw_data": lead,
            "email": None,
            "email_confidence": 0,
            "contact_name": lead.get("contact_name"),
            "contact_role": lead.get("contact_role"),
            "company_summary": None,
        })

    return normalized


async def lead_finder_agent(state: dict) -> dict:
    """
    Agent 1: Find raw leads from CSV file.
    """
    icp = state["icp"]
    raw_leads = []
    errors = state.get("errors", [])

    log.info(f"[LeadFinder] Starting for campaign {state.get('campaign_id')}")

    # Load from CSV file
    csv_path = "sample_leads.csv"
    if os.path.exists(csv_path):
        try:
            csv_leads = load_leads_from_csv(csv_path)
            raw_leads.extend(csv_leads)
            log.info(f"[LeadFinder] CSV loaded {len(csv_leads)} leads")
        except Exception as e:
            err = f"CSV load failed: {str(e)}"
            log.error(err)
            errors.append(err)
    else:
        log.warning(f"[LeadFinder] No CSV file found at {csv_path}")
        errors.append("No sample_leads.csv found")

    # Normalize & cap
    normalized = normalize_leads(raw_leads)
    capped = normalized[:settings.max_leads_per_run]

    log.info(f"[LeadFinder] Normalized {len(capped)} unique leads")

    state["raw_leads"] = capped
    state["errors"] = errors
    return state