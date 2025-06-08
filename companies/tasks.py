from celery import shared_task
from django.db import close_old_connections

from .financial_importer import import_financials
from .models import Company


@shared_task
def trigger_financial_import_task(company_id):
    """Import financial data for a company if not already available."""
    # Ensure Celery workers do not reuse stale database connections which can
    # lead to "database is locked" errors with SQLite
    close_old_connections()

    company = Company.objects.get(id=company_id)

    if not company.annual_accounts.exists():
        import_financials(company.number)
