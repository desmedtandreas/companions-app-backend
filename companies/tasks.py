from celery import shared_task
from .financial_importer import import_financials
from .models import Company
import time

@shared_task
def trigger_financial_import_task(company_id):
    """Import financial data for a company if not already available."""
    company = Company.objects.get(id=company_id)

    time.sleep(1)

    if not company.annual_accounts.exists():
        import_financials(company.number)
