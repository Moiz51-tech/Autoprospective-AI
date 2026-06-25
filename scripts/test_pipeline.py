#!/usr/bin/env python3
"""
Dry-run the full pipeline with test data (no real emails sent).
Usage: python scripts/test_pipeline.py [--dry-run]

--dry-run: Skips actual email sending (sets daily limit to 0)
"""
import asyncio
import sys
import os
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_CAMPAIGN = {
    "id": "test-001",
    "name": "Test Campaign — Marketing Agencies NYC",
    "sender_name": "John Smith",
    "sender_company": "AutoProspect Demo",
    "sender_email": "john@demo.com",
    "value_proposition": "We help marketing agencies automate lead generation, saving 10+ hours/week.",
    "social_proof": "AgencyX went from 2 to 8 clients in 60 days using our system.",
    "tone": "professional but friendly",
    "icp": {
        "keywords": ["marketing agency", "digital marketing"],
        "locations": ["New York"],
        "min_employees": 5,
        "max_employees": 100,
        "industries": ["marketing", "advertising"],
    },
}


async def main(dry_run: bool = False):
    from agents.graph import run_campaign
    from config import settings

    if dry_run:
        # Override daily limit so no emails go out
        settings.daily_email_limit = 0
        print("🔒 DRY RUN — no emails will be sent\n")

    print("🚀 Running test pipeline...")
    print(f"   Campaign: {TEST_CAMPAIGN['name']}")
    print(f"   ICP: {TEST_CAMPAIGN['icp']['keywords']} in {TEST_CAMPAIGN['icp']['locations']}\n")

    try:
        result = await run_campaign(TEST_CAMPAIGN)
        stats = result.get("run_stats", {})

        print("\n" + "=" * 50)
        print("✅ Pipeline Results")
        print("=" * 50)
        print(f"  Raw leads found:   {stats.get('raw_leads', 0)}")
        print(f"  Enriched:          {stats.get('enriched_leads', 0)}")
        print(f"  Hot leads:         {stats.get('hot_leads', 0)}")
        print(f"  Warm leads:        {stats.get('warm_leads', 0)}")
        print(f"  Cold leads:        {stats.get('cold_leads', 0)}")
        print(f"  Emails sent:       {stats.get('emails_sent', 0)}")
        print(f"  Emails failed:     {stats.get('emails_failed', 0)}")
        print(f"  Emails skipped:    {stats.get('emails_skipped', 0)}")
        print(f"  Errors:            {len(stats.get('errors', []))}")

        if stats.get("errors"):
            print("\nError details:")
            for err in stats["errors"]:
                print(f"  ⚠️  {err}")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test AutoProspect AI pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Skip email sending")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
