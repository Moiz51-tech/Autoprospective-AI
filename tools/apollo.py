import httpx
from config import settings
from utils.logger import get_logger
from utils.retry import with_retry

log = get_logger("apollo")


@with_retry(max_retries=3, delay=2.0)
async def search_apollo_companies(icp: dict) -> list:
    if settings.apollo_api_key == "placeholder":
        log.warning("Apollo API key is placeholder — returning empty results")
        return []

    headers = {
        "X-Api-Key": settings.apollo_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        payload = {
            "q_organization_keyword_tags": icp.get("keywords", []),
            "page": 1,
            "per_page": 50,
        }

        if icp.get("industries"):
            payload["organization_industry_tag_ids"] = icp["industries"]

        resp = await client.post(
            "https://api.apollo.io/v1/mixed_companies/search",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        companies = data.get("organizations", [])
        log.info(f"Apollo returned {len(companies)} companies")
        return companies


@with_retry(max_retries=3, delay=2.0)
async def find_contacts_at_company(domain: str, titles: list) -> list:
    if settings.apollo_api_key == "placeholder":
        return []

    headers = {
        "X-Api-Key": settings.apollo_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        payload = {
            "q_organization_domains": [domain],
            "person_titles": titles,
            "per_page": 5,
        }
        resp = await client.post(
            "https://api.apollo.io/v1/mixed_people/search",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("people", [])