import asyncio
import json
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

from tools.hunter import find_email
from tools.scraper import scrape_company_context
from config import settings
from utils.logger import get_logger

log = get_logger("lead_enricher")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=200,
    openai_api_key=settings.openai_api_key,
)

SUMMARIZE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a B2B sales research assistant. Summarize this company in EXACTLY 2 sentences. "
        "Focus on: what they do, who they serve, and any unique differentiator. Be specific and concrete.",
    ),
    ("human", "{text}"),
])


async def summarize_company(text: str) -> str:
    """Use GPT-4o-mini to summarize company About page content."""
    if not text or len(text) < 50:
        return ""
    try:
        chain = SUMMARIZE_PROMPT | llm
        response = await chain.ainvoke({"text": text[:3000]})
        return response.content.strip()
    except Exception as e:
        log.warning(f"LLM summarization failed: {e}")
        return ""


async def enrich_single_lead(lead: dict) -> dict:
    """Enrich one lead with email, contact info, and company context."""
    domain = lead.get("domain", "")
    if not domain:
        return lead

    # Run email finding and scraping in parallel
    email_task = find_email(domain, lead.get("contact_name"))
    context_task = scrape_company_context(domain)

    try:
        email_result, raw_text = await asyncio.gather(
            email_task, context_task, return_exceptions=True
        )

        if isinstance(email_result, dict):
            lead["email"] = email_result.get("email")
            lead["email_confidence"] = email_result.get("confidence", 0)

        company_summary = ""
        if isinstance(raw_text, str) and raw_text:
            company_summary = await summarize_company(raw_text)

        lead["company_summary"] = company_summary

    except Exception as e:
        log.warning(f"Enrichment failed for {domain}: {e}")

    return lead


async def lead_enricher_agent(state: dict) -> dict:
    """
    Agent 2: Enrich raw leads with emails, contact info, company context.
    Runs in parallel batches of 10 for speed.
    """
    raw_leads = state.get("raw_leads", [])
    log.info(f"[Enricher] Starting enrichment for {len(raw_leads)} leads")

    enriched = []
    batch_size = 10

    for i in range(0, len(raw_leads), batch_size):
        batch = raw_leads[i : i + batch_size]
        results = await asyncio.gather(
            *[enrich_single_lead(lead) for lead in batch],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, dict):
                enriched.append(r)

        log.info(f"[Enricher] Enriched {min(i + batch_size, len(raw_leads))}/{len(raw_leads)} leads")
        await asyncio.sleep(1)  # Rate limiting

    # Keep only leads with at least a domain
    valid = [l for l in enriched if l.get("domain")]
    log.info(f"[Enricher] Complete. {len(valid)} valid leads enriched")

    state["enriched_leads"] = valid
    return state
