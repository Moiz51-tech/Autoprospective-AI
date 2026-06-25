-- AutoProspect AI — Supabase Database Schema
-- Run this entire file in Supabase SQL Editor: Database > SQL Editor > New Query
-- Then click RUN.

-- Enable vector extension (for future semantic search on leads)
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────────────────────
-- CAMPAIGNS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    icp JSONB NOT NULL DEFAULT '{}',
    sender_name TEXT,
    sender_company TEXT,
    sender_email TEXT,
    value_proposition TEXT,
    social_proof TEXT,
    tone TEXT DEFAULT 'professional but friendly',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- LEADS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    company_name TEXT,
    domain TEXT UNIQUE,           -- Global deduplication by domain
    contact_name TEXT,
    contact_role TEXT,
    email TEXT,
    email_confidence INT DEFAULT 0 CHECK (email_confidence >= 0 AND email_confidence <= 100),
    linkedin_url TEXT,
    company_summary TEXT,
    score INT DEFAULT 0 CHECK (score >= 0 AND score <= 100),
    tier TEXT DEFAULT 'unscored' CHECK (tier IN ('hot', 'warm', 'cold', 'unscored')),
    score_reasons JSONB DEFAULT '[]',
    llm_reasoning TEXT,
    status TEXT DEFAULT 'new' CHECK (status IN ('new', 'queued', 'sent', 'replied', 'bounced', 'unsubscribed', 'skipped_no_email', 'skipped_no_message', 'send_failed', 'copywriting_failed')),
    source TEXT DEFAULT 'apollo' CHECK (source IN ('apollo', 'google_maps', 'manual')),
    employees INT,
    industry TEXT,
    location TEXT,
    tech_stack JSONB DEFAULT '[]',
    raw_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- MESSAGES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    subject TEXT,
    body TEXT,
    follow_up_1 TEXT,
    follow_up_2 TEXT,
    sequence_step INT DEFAULT 1 CHECK (sequence_step IN (1, 2, 3)),
    ab_variant TEXT DEFAULT 'A' CHECK (ab_variant IN ('A', 'B')),
    sent_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    replied_at TIMESTAMPTZ,
    bounced_at TIMESTAMPTZ,
    gmail_message_id TEXT,
    gmail_thread_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- CAMPAIGN RUNS (audit trail)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaign_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id TEXT,     -- TEXT not UUID so test campaigns work too
    run_at TIMESTAMPTZ,
    raw_leads INT DEFAULT 0,
    enriched_leads INT DEFAULT 0,
    hot_leads INT DEFAULT 0,
    warm_leads INT DEFAULT 0,
    cold_leads INT DEFAULT 0,
    emails_sent INT DEFAULT 0,
    emails_failed INT DEFAULT 0,
    emails_skipped INT DEFAULT 0,
    errors JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- LEARNING PATTERNS (what ICPs / messages convert best)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS learning_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_type TEXT,     -- 'icp_attribute', 'subject_pattern', 'tone'
    value TEXT,
    campaign_id TEXT,
    conversion_rate FLOAT DEFAULT 0,
    sample_size INT DEFAULT 1,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (pattern_type, value, campaign_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_leads_campaign_id ON leads(campaign_id);
CREATE INDEX IF NOT EXISTS idx_leads_tier ON leads(tier);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_domain ON leads(domain);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
CREATE INDEX IF NOT EXISTS idx_messages_lead_id ON messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_messages_campaign_id ON messages(campaign_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at);
CREATE INDEX IF NOT EXISTS idx_messages_step ON messages(sequence_step);
CREATE INDEX IF NOT EXISTS idx_campaign_runs_campaign ON campaign_runs(campaign_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- AUTO-UPDATE updated_at trigger
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY (RLS)
-- Use service role key from your backend — anon key is for frontend only.
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_patterns ENABLE ROW LEVEL SECURITY;

-- Allow full access when using service role key (your backend uses this)
CREATE POLICY "service_all" ON campaigns FOR ALL USING (true);
CREATE POLICY "service_all" ON leads FOR ALL USING (true);
CREATE POLICY "service_all" ON messages FOR ALL USING (true);
CREATE POLICY "service_all" ON campaign_runs FOR ALL USING (true);
CREATE POLICY "service_all" ON learning_patterns FOR ALL USING (true);
