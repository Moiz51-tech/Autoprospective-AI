import asyncio
from agents.lead_enricher import lead_enricher_agent
from agents.lead_scorer import lead_scorer_agent
from agents.copywriter import copywriter_agent

async def test():
    state = {
        'campaign_id': 'test-001',
        'campaign': {
            'id': 'test-001',
            'name': 'Test Campaign',
            'sender_name': 'Abdul Moiz',
            'sender_company': 'Moiz Agent Lab',
            'sender_email': 'abdulmoiz@gmail.com',
            'value_proposition': 'We build AI automation systems that save 10 hours per week',
            'social_proof': 'Helped 3 agencies automate their outreach',
            'tone': 'professional but friendly',
        },
        'icp': {'keywords': ['marketing agency'], 'min_employees': 5, 'max_employees': 100, 'industries': ['marketing']},
        'raw_leads': [
            {'company_name': 'Creative Spark Agency', 'domain': 'creativespark.com', 'employees': 20, 'industry': 'marketing', 'location': 'New York', 'source': 'apollo'},
            {'company_name': 'Digital Wave Media', 'domain': 'digitalwave.com', 'employees': 35, 'industry': 'marketing', 'location': 'New York', 'source': 'apollo'},
        ],
        'enriched_leads': [],
        'scored_leads': [],
        'outreach_queue': [],
        'sent_messages': [],
        'run_stats': None,
        'errors': [],
        'iteration': 0,
    }

    print('--- Enriching leads ---')
    state = await lead_enricher_agent(state)
    print('--- Scoring leads ---')
    state = await lead_scorer_agent(state)

    state['outreach_queue'] = [l for l in state['scored_leads'] if l['tier'] in ['hot', 'warm']]
    print(f'Leads in queue: {len(state["outreach_queue"])}')

    print('--- Writing emails ---')
    state = await copywriter_agent(state)

    for lead in state['outreach_queue']:
        print()
        print('=' * 50)
        print('Company:', lead.get('company_name'))
        print('Tier:', lead.get('tier'))
        print('Score:', lead.get('score'))
        msgs = lead.get('outreach_messages', {})
        print('Subject:', msgs.get('subject'))
        print()
        print('Email:')
        print(msgs.get('body', ''))

asyncio.run(test())