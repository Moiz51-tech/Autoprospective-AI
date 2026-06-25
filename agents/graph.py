"""
LangGraph orchestration for AutoProspect AI.
Defines the full multi-agent pipeline as a compiled state machine.
"""
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END

from agents.lead_finder import lead_finder_agent
from agents.lead_enricher import lead_enricher_agent
from agents.lead_scorer import lead_scorer_agent, route_by_score
from agents.copywriter import copywriter_agent
from agents.outreach import outreach_agent
from agents.analytics import analytics_agent
from utils.logger import get_logger

log = get_logger("graph")


class ProspectState(TypedDict):
    """Shared state object passed between all agents in the pipeline."""
    campaign_id: str
    campaign: dict           # Full campaign config
    icp: dict                # Ideal Customer Profile

    # Pipeline data (populated progressively)
    raw_leads: List[dict]
    enriched_leads: List[dict]
    scored_leads: List[dict]
    outreach_queue: List[dict]
    sent_messages: List[dict]

    # Outputs
    run_stats: Optional[dict]
    errors: List[str]
    iteration: int


def build_graph() -> StateGraph:
    """Build and compile the LangGraph state machine."""
    workflow = StateGraph(ProspectState)

    # Register all agents as nodes
    workflow.add_node("lead_finder", lead_finder_agent)
    workflow.add_node("lead_enricher", lead_enricher_agent)
    workflow.add_node("lead_scorer", lead_scorer_agent)
    workflow.add_node("copywriter", copywriter_agent)
    workflow.add_node("outreach", outreach_agent)
    workflow.add_node("analytics", analytics_agent)

    # Linear flow with conditional branching after scoring
    workflow.set_entry_point("lead_finder")
    workflow.add_edge("lead_finder", "lead_enricher")
    workflow.add_edge("lead_enricher", "lead_scorer")

    # Hot/warm → copywriter → outreach → analytics
    # Cold only → analytics directly
    workflow.add_conditional_edges(
        "lead_scorer",
        route_by_score,
        {
            "copywriter": "copywriter",
            "analytics": "analytics",
        },
    )
    workflow.add_edge("copywriter", "outreach")
    workflow.add_edge("outreach", "analytics")
    workflow.add_edge("analytics", END)

    return workflow.compile()


# Compiled app — module-level singleton
app = build_graph()


async def run_campaign(campaign: dict) -> dict:
    """
    Run the full AutoProspect pipeline for a campaign.

    Args:
        campaign: Campaign config dict. Expected keys:
            id, name, sender_name, sender_company, sender_email,
            value_proposition, social_proof, tone, icp (dict)

    Returns:
        Final ProspectState dict containing run_stats and all pipeline data.
    """
    campaign_name = campaign.get("name", "Unknown")
    campaign_id = campaign.get("id", "unknown")
    log.info(f"=== Campaign start: {campaign_name} ({campaign_id}) ===")

    # Normalize ICP — ensure it's a dict, not a Pydantic model
    icp = campaign.get("icp", {})
    if hasattr(icp, "model_dump"):
        icp = icp.model_dump()

    initial_state: ProspectState = {
        "campaign_id": campaign_id,
        "campaign": campaign,
        "icp": icp,
        "raw_leads": [],
        "enriched_leads": [],
        "scored_leads": [],
        "outreach_queue": [],
        "sent_messages": [],
        "run_stats": None,
        "errors": [],
        "iteration": 0,
    }

    try:
        final_state = await app.ainvoke(initial_state)
        stats = final_state.get("run_stats", {})
        log.info(
            f"=== Campaign {campaign_id} complete | "
            f"Sent: {stats.get('emails_sent', 0)} | "
            f"Errors: {len(stats.get('errors', []))} ==="
        )
        return final_state
    except Exception as e:
        log.error(f"Campaign {campaign_id} pipeline failed: {e}", exc_info=True)
        raise
