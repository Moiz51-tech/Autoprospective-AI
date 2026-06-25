import csv
from utils.logger import get_logger

log = get_logger("csv_leads")

def load_leads_from_csv(filepath: str) -> list:
    """Load leads from a CSV file."""
    leads = []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append({
                'company_name': row.get('company_name', ''),
                'domain': row.get('domain', ''),
                'employees': int(row.get('employees', 0) or 0),
                'industry': row.get('industry', ''),
                'location': row.get('location', ''),
                'contact_name': row.get('contact_name', ''),
                'contact_role': row.get('contact_role', ''),
                'source': 'csv',
            })
    log.info(f"Loaded {len(leads)} leads from {filepath}")
    return leads