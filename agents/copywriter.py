import asyncio
import json
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

from config import settings
from utils.logger import get_logger

log = get_logger("copywriter")

# Use GPT-4o for hot leads (best quality), GPT-4o-mini for warm (cost savings)
llm_hot = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,
    openai_api_key=settings.openai_api_key,
)
llm_warm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    openai_api_key=settings.openai_api_key,
)

COPYWRITER_SYSTEM = """You are a world-class B2B cold email copywriter. You write emails that actually get replies.

Your emails are:
- Specific (reference something REAL and unique about the company)
- Short (under 180 words for body)
- Human (no corporate jargon, sounds like a person wrote it)
- Curiosity-driven (not a pitch dump)
- Single clear CTA only

NEVER use these phrases:
"I hope this email finds you well"
"I wanted to reach out"
"I came across your profile"
"synergy" / "leverage" / "game-changer" / "revolutionary" / "cutting-edge"

ALWAYS return valid JSON and absolutely nothing else — no markdown, no preamble."""

COPYWRITER_PROMPT = """Generate a cold outreach email sequence for this lead.

SENDER:
- Name: {sender_name}
- Company: {sender_company}
- Value Proposition: {value_prop}
- Social Proof: {social_proof}
- Tone: {tone}

LEAD:
- Name: {lead_name}
- Company: {lead_company}
- Role: {lead_role}
- Industry: {lead_industry}
- Company Context: {company_summary}
- Why They're a Fit: {score_reasons}

EMAIL STRUCTURE:
- Subject: personalized, curiosity-driven, 6-8 words max, NO question marks
- Body paragraph 1: one specific observation about THEIR company/situation (not generic flattery)
- Body paragraph 2: what you do and the specific result it creates (one sentence)
- Body paragraph 3: soft CTA — 15-min call OR reply to confirm interest
- Follow-up 1 (send day 3): completely different angle, 2-3 sentences
- Follow-up 2 (send day 7): final short nudge, 1-2 sentences, soft close

Return this JSON exactly:
{{
  "subject": "subject line here",
  "body": "email body here (use \\n\\n between paragraphs)",
  "follow_up_1": "day-3 follow-up text",
  "follow_up_2": "day-7 final follow-up text"
}}"""


async def generate_outreach(lead: dict, campaign: dict) -> dict:
    """Generate personalized email sequence for a single lead."""
    tier = lead.get("tier", "warm")
    llm = llm_hot if tier == "hot" else llm_warm

    prompt = ChatPromptTemplate.from_messages([
        ("system", COPYWRITER_SYSTEM),
        ("human", COPYWRITER_PROMPT),
    ])
    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "sender_name": campaign.get("sender_name", ""),
            "sender_company": campaign.get("sender_company", ""),
            "value_prop": campaign.get("value_proposition", ""),
            "social_proof": campaign.get("social_proof", "No specific case study yet"),
            "tone": campaign.get("tone", "professional but friendly"),
            "lead_name": lead.get("contact_name") or "there",
            "lead_company": lead.get("company_name", "your company"),
            "lead_role": lead.get("contact_role") or "Decision Maker",
            "lead_industry": lead.get("industry", "your industry"),
            "company_summary": lead.get("company_summary") or "No website data available",
            "score_reasons": ", ".join(lead.get("score_reasons", [])) or "general fit",
        })

        # Clean and parse JSON
        raw = response.content.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        messages = json.loads(raw)
        lead["outreach_messages"] = messages
        lead["status"] = "ready_to_send"
        log.debug(f"[Copywriter] Generated email for {lead.get('company_name')} | Subject: {messages.get('subject')}")

    except json.JSONDecodeError as e:
        log.warning(f"[Copywriter] JSON parse failed for {lead.get('company_name')}: {e}")
        lead["status"] = "copywriting_failed"
        lead["outreach_messages"] = {}
    except Exception as e:
        log.error(f"[Copywriter] Generation failed for {lead.get('company_name')}: {e}")
        lead["status"] = "copywriting_failed"
        lead["outreach_messages"] = {}

    return lead


async def generate_ab_variants(lead: dict, campaign: dict) -> dict:
    """Generate email + A/B subject line variant."""
    lead = await generate_outreach(lead, campaign)

    if lead.get("outreach_messages") and lead["outreach_messages"].get("subject"):
        original_subject = lead["outreach_messages"]["subject"]
        alt_prompt = f"""Generate 1 alternative subject line for this cold email.
Original: "{original_subject}"
Company: {lead.get('company_name', '')}
Industry: {lead.get('industry', '')}
Rules: 6-8 words, different angle from original, no question marks.
Return ONLY the subject line text, nothing else."""

        try:
            alt_resp = await llm_warm.ainvoke(alt_prompt)
            lead["outreach_messages"]["subject_b"] = alt_resp.content.strip().strip('"')
        except Exception:
            pass  # A/B variant is optional

    return lead


async def copywriter_agent(state: dict) -> dict:
    """
    Agent 4: Generate personalized email sequences for all hot/warm leads.
    Uses GPT-4o for hot leads, GPT-4o-mini for warm (3x cost savings).
    """
    campaign = state["campaign"]
    queue = state.get("outreach_queue", [])
    log.info(f"[Copywriter] Writing emails for {len(queue)} leads")

    results = []
    batch_size = 20

    for i in range(0, len(queue), batch_size):
        batch = queue[i : i + batch_size]
        batch_results = await asyncio.gather(
            *[generate_ab_variants(lead, campaign) for lead in batch],
            return_exceptions=True,
        )
        for r in batch_results:
            if isinstance(r, dict):
                results.append(r)
        await asyncio.sleep(2)  # Rate limit buffer

    success = sum(1 for l in results if l.get("status") == "ready_to_send")
    log.info(f"[Copywriter] Complete. {success}/{len(queue)} emails generated successfully")

    state["outreach_queue"] = results
    return state
