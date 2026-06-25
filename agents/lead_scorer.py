import asyncio
import json
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

from config import settings
from utils.logger import get_logger

log = get_logger("lead_scorer")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    openai_api_key=settings.openai_api_key,
)

WARM_LEAD_VALIDATOR_PROMPT = ChatPromptTemplate.from_template(
    """You are a B2B sales qualification expert.

ICP (Ideal Customer Profile):
{icp}

Lead Profile:
- Company: {company_name}
- Summary: {company_summary}
- Size: {employees} employees
- Industry: {industry}
- Why flagged as potential fit: {score_reasons}
- Algorithmic score: {score}/100

TASK: Decide if this lead should receive cold outreach.
Return JSON only, no markdown: {{"decision": "send" or "skip", "reason": "one sentence explaining why"}}"""
)


def calculate_base_score(lead: dict, icp: dict) -> tuple:
    """Rule-based scoring. Returns (score: int, reasons: list)."""
    score = 0
    reasons = []

    # Email quality
    confidence = lead.get("email_confidence", 0)
    if confidence >= 75:
        score += 20
        reasons.append("verified_email")
    elif lead.get("email"):
        score += 10
        reasons.append("email_found")

    # Company size match
    employees = lead.get("employees", 0)
    min_e = icp.get("min_employees", 1)
    max_e = icp.get("max_employees", 500)
    if employees and min_e <= employees <= max_e:
        score += 25
        reasons.append("size_match")

    # LinkedIn presence
    if lead.get("linkedin_url"):
        score += 10
        reasons.append("linkedin_present")

    # Industry match
    icp_industries = [i.lower() for i in icp.get("industries", [])]
    if icp_industries and lead.get("industry", "").lower() in icp_industries:
        score += 20
        reasons.append("industry_match")

    # Website verified (has company summary = scraped successfully)
    if lead.get("company_summary") and len(lead["company_summary"]) > 30:
        score += 10
        reasons.append("website_verified")

    # Tech stack match
    target_tech = [t.lower() for t in icp.get("target_tech", [])]
    lead_tech = [t.lower() for t in lead.get("tech_stack", [])]
    if target_tech and any(t in lead_tech for t in target_tech):
        score += 15
        reasons.append("tech_match")

    return score, reasons


async def llm_validate_warm_lead(lead: dict, icp: dict) -> str:
    """Use LLM to make final call on borderline (40-64 score) leads."""
    try:
        chain = WARM_LEAD_VALIDATOR_PROMPT | llm
        result = await chain.ainvoke({
            "icp": json.dumps(icp, indent=2),
            "company_name": lead.get("company_name", "Unknown"),
            "company_summary": lead.get("company_summary", "No website data"),
            "employees": lead.get("employees", "unknown"),
            "industry": lead.get("industry", "unknown"),
            "score_reasons": ", ".join(lead.get("score_reasons", [])),
            "score": lead.get("score", 0),
        })
        decision = json.loads(result.content)
        tier = "warm" if decision.get("decision") == "send" else "cold"
        lead["llm_reasoning"] = decision.get("reason", "")
        return tier
    except Exception as e:
        log.warning(f"LLM validation failed for {lead.get('company_name')}: {e}")
        return "warm"  # Default to warm if LLM fails


async def score_lead(lead: dict, icp: dict) -> dict:
    """Score a single lead and assign tier: hot / warm / cold."""
    score, reasons = calculate_base_score(lead, icp)
    lead["score"] = score
    lead["score_reasons"] = reasons

    if score >= 65:
        lead["tier"] = "hot"
    elif score >= 40:
        # Use LLM for borderline cases only (cost optimization)
        lead["tier"] = await llm_validate_warm_lead(lead, icp)
    else:
        lead["tier"] = "cold"

    return lead


async def lead_scorer_agent(state: dict) -> dict:
    """
    Agent 3: Score enriched leads and label hot / warm / cold.
    Hot (65+): Clear fit, prioritize immediately
    Warm (40-64): Borderline, LLM validates
    Cold (<40): Not a fit, skip outreach
    """
    icp = state["icp"]
    enriched_leads = state.get("enriched_leads", [])
    log.info(f"[Scorer] Scoring {len(enriched_leads)} leads")

    scored = []
    results = await asyncio.gather(
        *[score_lead(lead, icp) for lead in enriched_leads],
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, dict):
            scored.append(r)

    hot = sum(1 for l in scored if l["tier"] == "hot")
    warm = sum(1 for l in scored if l["tier"] == "warm")
    cold = sum(1 for l in scored if l["tier"] == "cold")

    log.info(f"[Scorer] Results — Hot: {hot} | Warm: {warm} | Cold: {cold}")

    state["scored_leads"] = scored
    return state


def route_by_score(state: dict) -> str:
    """LangGraph conditional edge router."""
    actionable = [l for l in state.get("scored_leads", []) if l["tier"] in ["hot", "warm"]]
    if actionable:
        state["outreach_queue"] = actionable
        return "copywriter"
    log.info("[Router] No actionable leads — routing to analytics")
    return "analytics"
