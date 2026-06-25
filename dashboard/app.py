import streamlit as st
import httpx
import pandas as pd
from datetime import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

st.set_page_config(
    page_title="AutoProspect AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

BACKEND_URL = settings.backend_url

# ── API client with auth ──────────────────────────────────
def api_get(path: str, params: dict = None):
    """Make authenticated GET request to backend."""
    headers = {"X-API-Key": settings.api_secret_key}
    try:
        resp = httpx.get(f"{BACKEND_URL}{path}", headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, json: dict = None):
    """Make authenticated POST request to backend."""
    headers = {"X-API-Key": settings.api_secret_key, "Content-Type": "application/json"}
    try:
        resp = httpx.post(f"{BACKEND_URL}{path}", headers=headers, json=json, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_put(path: str):
    headers = {"X-API-Key": settings.api_secret_key}
    try:
        resp = httpx.put(f"{BACKEND_URL}{path}", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ── Sidebar ───────────────────────────────────────────────
st.sidebar.markdown("# 🤖 AutoProspect AI")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Dashboard", "🚀 New Campaign", "👥 Leads", "📧 Messages", "⚙️ Settings"],
)

# ── Dashboard ─────────────────────────────────────────────
if page == "📊 Dashboard":
    st.title("📊 AutoProspect AI — Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Load data
    try:
        from tools.supabase_client import supabase
        leads = supabase.table("leads").select("*").execute().data or []
        messages = supabase.table("messages").select("*").execute().data or []
        campaigns = supabase.table("campaigns").select("*").execute().data or []
        runs = supabase.table("campaign_runs").select("*").order("run_at", desc=True).limit(10).execute().data or []
    except Exception as e:
        st.error(f"Could not connect to database: {e}")
        st.info("Check your .env file has correct SUPABASE_URL and SUPABASE_KEY.")
        st.stop()

    # ── Key metrics ──
    total_sent = sum(1 for m in messages if m.get("sent_at"))
    total_replied = sum(1 for m in messages if m.get("replied_at"))
    reply_rate = f"{(total_replied / max(total_sent, 1) * 100):.1f}%"

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Campaigns", len(campaigns))
    col2.metric("Total Leads", len(leads))
    col3.metric("Hot Leads 🔥", sum(1 for l in leads if l.get("tier") == "hot"))
    col4.metric("Emails Sent", total_sent)
    col5.metric("Replies", total_replied)
    col6.metric("Reply Rate", reply_rate)

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Lead Tier Distribution")
        if leads:
            tier_counts = pd.DataFrame(leads)["tier"].value_counts()
            tier_df = tier_counts.reset_index()
            tier_df.columns = ["Tier", "Count"]
            st.bar_chart(tier_df.set_index("Tier"))
        else:
            st.info("No leads yet.")

    with col_b:
        st.subheader("Recent Campaign Runs")
        if runs:
            run_df = pd.DataFrame(runs)[[
                "campaign_id", "emails_sent", "hot_leads", "warm_leads", "cold_leads", "run_at"
            ]].head(8)
            run_df["run_at"] = pd.to_datetime(run_df["run_at"]).dt.strftime("%m/%d %H:%M")
            st.dataframe(run_df, use_container_width=True)
        else:
            st.info("No campaign runs yet.")

    st.divider()
    st.subheader("Active Campaigns")
    if campaigns:
        camp_df = pd.DataFrame(campaigns)[["name", "status", "sender_email", "created_at"]].head(10)
        camp_df["created_at"] = pd.to_datetime(camp_df["created_at"]).dt.strftime("%Y-%m-%d")

        for _, row in camp_df.iterrows():
            col_x, col_y, col_z = st.columns([4, 2, 2])
            with col_x:
                st.write(f"**{row['name']}** — `{row['status']}`")
            with col_y:
                camp_id = campaigns[camp_df.index.get_loc(_)]["id"] if _ in camp_df.index else None
    else:
        st.info("No campaigns yet. Create one to get started!")

    if st.button("🔄 Refresh"):
        st.rerun()


# ── New Campaign ──────────────────────────────────────────
elif page == "🚀 New Campaign":
    st.title("🚀 Launch New Campaign")

    with st.form("new_campaign"):
        st.subheader("Sender Details")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Campaign Name *", placeholder="Q4 Marketing Agencies NYC")
            sender_name = st.text_input("Your Name *", placeholder="John Smith")
            sender_company = st.text_input("Your Company *", placeholder="Acme Corp")
        with col2:
            sender_email = st.text_input("Sender Email *", placeholder="john@acme.com")
            tone = st.selectbox(
                "Email Tone",
                ["professional but friendly", "casual", "formal", "startup-friendly"],
            )

        st.divider()
        st.subheader("Messaging")
        value_prop = st.text_area(
            "Value Proposition *",
            placeholder="We help marketing agencies automate lead generation, saving 10+ hours/week and tripling client pipeline.",
            height=80,
        )
        social_proof = st.text_area(
            "Social Proof (optional)",
            placeholder="AgencyX grew from 2 to 8 clients in 60 days using our system.",
            height=60,
        )

        st.divider()
        st.subheader("Ideal Customer Profile (ICP)")
        col3, col4 = st.columns(2)
        with col3:
            keywords = st.text_input(
                "Target Keywords * (comma-separated)",
                placeholder="marketing agency, digital marketing, SEO agency",
            )
            locations = st.text_input("Target Locations (comma-separated)", value="United States")
            min_employees = st.number_input("Min Employees", value=5, min_value=1)
        with col4:
            industries = st.text_input(
                "Industries (comma-separated)", placeholder="marketing, advertising, media"
            )
            max_employees = st.number_input("Max Employees", value=100, min_value=1)
            local_business = st.checkbox("Local Business (use Google Maps)")

        submitted = st.form_submit_button("🚀 Launch Campaign", type="primary")

        if submitted:
            required = [name, sender_name, sender_company, sender_email, value_prop, keywords]
            if not all(f.strip() for f in required):
                st.error("Please fill in all required (*) fields.")
            elif max_employees < min_employees:
                st.error("Max employees must be >= min employees.")
            else:
                payload = {
                    "name": name.strip(),
                    "sender_name": sender_name.strip(),
                    "sender_company": sender_company.strip(),
                    "sender_email": sender_email.strip(),
                    "value_proposition": value_prop.strip(),
                    "social_proof": social_proof.strip() or "Results-driven approach",
                    "tone": tone,
                    "icp": {
                        "keywords": [k.strip() for k in keywords.split(",") if k.strip()],
                        "locations": [l.strip() for l in locations.split(",") if l.strip()],
                        "industries": [i.strip() for i in industries.split(",") if i.strip()] if industries else [],
                        "min_employees": min_employees,
                        "max_employees": max_employees,
                        "local_business": local_business,
                    },
                }

                with st.spinner("Creating campaign..."):
                    result = api_post("/api/campaigns/create", json=payload)

                if result:
                    st.success(f"✅ Campaign '{name}' created! ID: `{result['id']}`")
                    st.info("Go to **Dashboard** to monitor progress, or use the campaign ID to trigger a run via the API.")


# ── Leads ─────────────────────────────────────────────────
elif page == "👥 Leads":
    st.title("👥 Lead Database")

    try:
        from tools.supabase_client import supabase

        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            tier_filter = st.selectbox("Filter by Tier", ["All", "hot", "warm", "cold"])
        with col_f2:
            campaigns = supabase.table("campaigns").select("id,name").execute().data or []
            camp_options = {"All": None}
            camp_options.update({c["name"]: c["id"] for c in campaigns})
            camp_filter = st.selectbox("Filter by Campaign", list(camp_options.keys()))
        with col_f3:
            st.write("")
            st.write("")
            export_btn = st.button("📥 Export CSV")

        query = supabase.table("leads").select("*").order("score", desc=True).limit(500)
        if tier_filter != "All":
            query = query.eq("tier", tier_filter)
        if camp_filter != "All":
            query = query.eq("campaign_id", camp_options[camp_filter])

        leads = query.execute().data or []

        if leads:
            df = pd.DataFrame(leads)
            display_cols = [c for c in [
                "company_name", "domain", "contact_name", "email",
                "email_confidence", "tier", "score", "status", "industry", "created_at"
            ] if c in df.columns]
            display_df = df[display_cols].copy()
            if "created_at" in display_df.columns:
                display_df["created_at"] = pd.to_datetime(display_df["created_at"]).dt.strftime("%Y-%m-%d")

            def color_tier(val):
                colors = {
                    "hot": "background-color: #ffcccc; color: #990000",
                    "warm": "background-color: #fff3cc; color: #664400",
                    "cold": "background-color: #e8e8e8; color: #444",
                }
                return colors.get(val, "")

            st.write(f"**{len(leads)} leads found**")
            st.dataframe(
                display_df.style.applymap(color_tier, subset=["tier"]),
                use_container_width=True,
                height=500,
            )

            if export_btn:
                csv = display_df.to_csv(index=False)
                st.download_button(
                    "⬇️ Download CSV",
                    csv,
                    f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    "text/csv",
                )
        else:
            st.info("No leads found. Run a campaign first!")

    except Exception as e:
        st.error(f"Failed to load leads: {e}")


# ── Messages ──────────────────────────────────────────────
elif page == "📧 Messages":
    st.title("📧 Outreach Messages")

    try:
        from tools.supabase_client import supabase
        messages = supabase.table("messages").select(
            "*, leads(company_name, email, tier)"
        ).order("sent_at", desc=True).limit(200).execute().data or []

        if messages:
            total_sent = sum(1 for m in messages if m.get("sent_at"))
            total_replied = sum(1 for m in messages if m.get("replied_at"))
            a_count = sum(1 for m in messages if m.get("ab_variant") == "A")
            b_count = sum(1 for m in messages if m.get("ab_variant") == "B")

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total Sent", total_sent)
            col2.metric("Replies", total_replied)
            col3.metric("Reply Rate", f"{(total_replied / max(total_sent, 1) * 100):.1f}%")
            col4.metric("A/B Variant A", a_count)
            col5.metric("A/B Variant B", b_count)

            st.divider()

            seq_filter = st.selectbox("Filter by sequence step", ["All", "1 (Initial)", "2 (Day-3)", "3 (Day-7)"])

            for msg in messages[:100]:
                step = msg.get("sequence_step", 1)
                if seq_filter != "All" and str(step) != seq_filter[0]:
                    continue

                lead = msg.get("leads") or {}
                replied = "✅ Replied" if msg.get("replied_at") else "📨 Sent"
                label = f"{replied} | {lead.get('company_name', 'Unknown')} | {msg.get('subject', 'No subject')} | Step {step}"

                with st.expander(label):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**To:** {lead.get('email', 'N/A')}")
                        st.write(f"**Sent:** {msg.get('sent_at', 'N/A')}")
                        st.write(f"**Step:** {step}")
                    with col_b:
                        st.write(f"**Lead Tier:** {lead.get('tier', 'N/A')}")
                        st.write(f"**A/B Variant:** {msg.get('ab_variant', 'A')}")
                        st.write(f"**Replied:** {'Yes ✅' if msg.get('replied_at') else 'No'}")

                    st.text_area(
                        "Email Body",
                        msg.get("body", ""),
                        height=120,
                        key=f"body_{msg['id']}",
                        disabled=True,
                    )
        else:
            st.info("No messages sent yet. Run a campaign to start outreach!")

    except Exception as e:
        st.error(f"Failed to load messages: {e}")


# ── Settings ──────────────────────────────────────────────
elif page == "⚙️ Settings":
    st.title("⚙️ System Settings")

    st.subheader("Environment Status")
    from config import settings as cfg

    checks = {
        "OpenAI API Key": cfg.openai_api_key != "sk-placeholder",
        "Apollo API Key": cfg.apollo_api_key != "placeholder",
        "Hunter.io API Key": cfg.hunter_api_key != "placeholder",
        "Google Maps API Key": cfg.google_maps_api_key != "placeholder",
        "Supabase URL": cfg.supabase_url != "https://placeholder.supabase.co",
        "Gmail Credentials": os.path.exists(cfg.gmail_credentials_path),
        "Gmail Token": os.path.exists(cfg.gmail_token_path),
        "API Secret Key": cfg.api_secret_key != "change-this-secret-key-in-production-use-long-random-string",
    }

    for key, ok in checks.items():
        icon = "✅" if ok else "❌"
        st.write(f"{icon} **{key}**: {'Configured' if ok else 'Not configured'}")

    st.divider()
    st.subheader("Current Limits")
    st.write(f"**Max leads per run:** {cfg.max_leads_per_run}")
    st.write(f"**Daily email limit:** {cfg.daily_email_limit}")
    st.write(f"**Backend URL:** {cfg.backend_url}")

    st.divider()
    st.subheader("Quick Actions")
    if st.button("🔐 Setup Gmail Auth"):
        st.info("Run in terminal: `python scripts/setup_gmail.py`")
    if st.button("🔑 Generate API Keys"):
        st.info("Run in terminal: `python scripts/generate_api_key.py`")
