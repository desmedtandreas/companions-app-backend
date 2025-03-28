from django.core.management.base import BaseCommand
from companies.models import Company

class Command(BaseCommand):
    help = "Normalize VAT numbers by removing dots (bulk update)"

    def handle(self, *args, **kwargs):
        batch_size = 1000
        updated_total = 0
        batch = []

        for company in Company.objects.iterator(chunk_size=batch_size):
            clean_vat = company.number.replace('.', '')
            if clean_vat != company.number:
                company.number = clean_vat
                batch.append(company)

            if len(batch) >= batch_size:
                Company.objects.bulk_update(batch, ['number'])
                updated_total += len(batch)
                batch = []

        if batch:
            Company.objects.bulk_update(batch, ['number'])
            updated_total += len(batch)

        self.stdout.write(self.style.SUCCESS(f"{updated_total} VAT numbers normalized."))
