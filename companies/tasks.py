from celery import shared_task
from .financial_importer import import_financials # wherever your function is
from .models import Company
import time

@shared_task
def trigger_financial_import_task(company_id):
    company = Company.objects.get(id=company_id)
    
    time.sleep(2)
    
    financials = company.annual_accounts.all()
    if not financials.exists():
        import_financials(company.number)
    else:
        pass