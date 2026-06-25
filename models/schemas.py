from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


class ICP(BaseModel):
    keywords: List[str] = Field(default_factory=list, description="Target keywords e.g. ['marketing agency']")
    locations: List[str] = Field(default_factory=lambda: ["United States"])
    min_employees: int = Field(default=5, ge=1)
    max_employees: int = Field(default=500, ge=1)
    industries: List[str] = Field(default_factory=list)
    target_tech: List[str] = Field(default_factory=list)
    local_business: bool = False
    service_keyword: Optional[str] = None
    decision_maker_titles: List[str] = Field(
        default_factory=lambda: ["CEO", "Founder", "Owner", "Director", "VP of Marketing"]
    )

    @field_validator("keywords")
    @classmethod
    def keywords_not_empty(cls, v):
        if not v:
            raise ValueError("At least one keyword is required")
        return v

    @field_validator("max_employees")
    @classmethod
    def max_greater_than_min(cls, v, info):
        if "min_employees" in info.data and v < info.data["min_employees"]:
            raise ValueError("max_employees must be >= min_employees")
        return v


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    icp: ICP
    sender_name: str = Field(min_length=1, max_length=100)
    sender_company: str = Field(min_length=1, max_length=100)
    sender_email: str = Field(min_length=5, max_length=200)
    value_proposition: str = Field(min_length=10, max_length=1000)
    social_proof: Optional[str] = Field(default="Results-driven approach with proven track record", max_length=500)
    tone: str = Field(default="professional but friendly")

    @field_validator("tone")
    @classmethod
    def valid_tone(cls, v):
        allowed = ["professional but friendly", "casual", "formal", "startup-friendly"]
        if v not in allowed:
            raise ValueError(f"tone must be one of: {allowed}")
        return v


class CampaignResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    icp: Dict[str, Any]


class LeadResponse(BaseModel):
    id: str
    campaign_id: str
    company_name: Optional[str]
    domain: Optional[str]
    contact_name: Optional[str]
    contact_role: Optional[str]
    email: Optional[str]
    email_confidence: Optional[int]
    linkedin_url: Optional[str]
    company_summary: Optional[str]
    score: int
    tier: str
    score_reasons: Optional[List[str]]
    status: str
    created_at: datetime


class OutreachMessage(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=10, max_length=2000)
    follow_up_1: Optional[str] = None
    follow_up_2: Optional[str] = None
    subject_b: Optional[str] = None  # A/B variant


class CampaignRunResult(BaseModel):
    campaign_id: str
    raw_leads: int
    enriched_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    emails_sent: int
    errors: List[str]
