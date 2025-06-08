from celery import shared_task
from .financial_importer import import_financials
from .models import Company


@shared_task
def trigger_financial_import_task(company_id):
    """Import financial data for a company if not already available."""
    company = Company.objects.get(id=company_id)

    if not company.annual_accounts.exists():
        import_financials(company.number)
