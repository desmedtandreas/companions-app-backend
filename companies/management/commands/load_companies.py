import csv
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from companies.models import Company, Address

class Command(BaseCommand):
    help = 'Load companies from CSV files (enterprise, denomination, addresses)'

    def handle(self, *args, **options):
        self.load_companies('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/enterprise.csv')
        self.load_denomination('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/denomination.csv')
        self.load_addresses('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address.csv')

        self.stdout.write(self.style.SUCCESS('✅ Successfully loaded all data.'))

    def stream_csv(self, url, delimiter=';'):
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            lines = (line.decode('utf-8') for line in response.iter_lines())
            reader = csv.DictReader(lines, delimiter=delimiter)
            for row in reader:
                yield row
                
    def parse_date(self, date_str):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            return None

    def load_companies(self, url):
        existing_numbers = set(Company.objects.values_list('number', flat=True))
        new_companies = []
        count = 0

        for row in self.stream_csv(url, delimiter=';'):
            enterprise_number = row['EnterpriseNumber']
            if enterprise_number not in existing_numbers:
                new_companies.append(Company(
                    number=enterprise_number,
                    status=row['JuridicalSituation'],
                    type=row['TypeOfEnterprise'],
                    start_date=self.parse_date(row['StartDate'])
                ))
                count += 1

            if len(new_companies) >= 500:
                Company.objects.bulk_create(new_companies, batch_size=500)
                new_companies.clear()

        if new_companies:
            Company.objects.bulk_create(new_companies, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f'🚀 { count } Companies loaded incrementally.'))

    def load_denomination(self, url):
        batch_size = 500
        denom_batch = {}
        count = 0

        for row in self.stream_csv(url, delimiter=';'):
            count += 1
            denom_batch[row['EntityNumber']] = row['Denomination']

            if len(denom_batch) >= batch_size:
                self._update_company_names(denom_batch)
                denom_batch.clear()
                

        if denom_batch:
            self._update_company_names(denom_batch)

        self.stdout.write(self.style.SUCCESS(f'📝 {count} Denominations updated incrementally.'))

    def _update_company_names(self, denom_map):
        companies = Company.objects.filter(number__in=denom_map.keys())
        companies_to_update = []
        for company in companies:
            new_name = denom_map.get(company.number)
            if new_name and not company.name:
                company.name = new_name
                companies_to_update.append(company)

        if companies_to_update:
            Company.objects.bulk_update(companies_to_update, ['name'], batch_size=500)

    def load_addresses(self, url):
        batch_size = 500
        address_batch = []
        company_cache = {}
        count = 0

        for row in self.stream_csv(url, delimiter=';'):
            enterprise_number = row['EntityNumber']
            if enterprise_number not in company_cache:
                try:
                    company_cache[enterprise_number] = Company.objects.get(number=enterprise_number)
                except Company.DoesNotExist:
                    continue  # Skip if no matching company found

            count += 1
            company = company_cache[enterprise_number]
            address_batch.append(Address(
                company=company,
                type=row['TypeOfAddress'],
                street=row['Street'],
                house_number=row['HouseNumber'],
                postal_code=row['Zipcode'],
                city=row['Municipality'],
            ))

            if len(address_batch) >= batch_size:
                Address.objects.bulk_create(address_batch, batch_size=500)
                address_batch.clear()

        if address_batch:
            Address.objects.bulk_create(address_batch, batch_size=500)

        self.stdout.write(self.style.SUCCESS(f'🏠 {count} Addresses loaded incrementally.'))