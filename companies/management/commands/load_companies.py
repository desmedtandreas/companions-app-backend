import csv
import requests
from django.core.management.base import BaseCommand
from companies.models import Company, Address

class Command(BaseCommand):
    help = 'Load companies from CSV files (enterprise, denomination, addresses)'

    def handle(self, *args, **options):
        self.load_companies('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/enterprise.csv')
        self.load_denomination('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/denomination.csv')
        self.load_addresses('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address.csv')

        self.stdout.write(self.style.SUCCESS('✅ Successfully loaded all data.'))

    def stream_csv(self, url):
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            lines = (line.decode('utf-8') for line in response.iter_lines())
            reader = csv.DictReader(lines)
            for row in reader:
                yield row

    def load_companies(self, url):
        existing_numbers = set(Company.objects.values_list('enterprise_number', flat=True))
        new_companies = []

        for row in self.stream_csv(url):
            if row['TypeOfEnterprise'] != '2':
                continue
            enterprise_number = row['EnterpriseNumber']
            if enterprise_number not in existing_numbers:
                new_companies.append(Company(
                    enterprise_number=enterprise_number,
                    legal_form=row['JuridicalForm']
                ))

            if len(new_companies) >= 500:
                Company.objects.bulk_create(new_companies, batch_size=500)
                new_companies.clear()

        if new_companies:
            Company.objects.bulk_create(new_companies, batch_size=500)
        self.stdout.write(self.style.SUCCESS('🚀 Companies loaded incrementally.'))

    def load_denomination(self, url):
        batch_size = 500
        denom_batch = {}

        for row in self.stream_csv(url):
            if row['TypeOfDenomination'] != '001':
                continue
            denom_batch[row['EntityNumber']] = row['Denomination']

            if len(denom_batch) >= batch_size:
                self._update_company_names(denom_batch)
                denom_batch.clear()

        if denom_batch:
            self._update_company_names(denom_batch)

        self.stdout.write(self.style.SUCCESS('📝 Denominations updated incrementally.'))

    def _update_company_names(self, denom_map):
        companies = Company.objects.filter(enterprise_number__in=denom_map.keys())
        companies_to_update = []
        for company in companies:
            new_name = denom_map.get(company.enterprise_number)
            if new_name and not company.name:
                company.name = new_name
                companies_to_update.append(company)

        if companies_to_update:
            Company.objects.bulk_update(companies_to_update, ['name'], batch_size=500)

    def load_addresses(self, url):
        batch_size = 500
        address_batch = []
        company_cache = {}

        for row in self.stream_csv(url):
            enterprise_number = row['EntityNumber']
            if enterprise_number not in company_cache:
                try:
                    company_cache[enterprise_number] = Company.objects.get(enterprise_number=enterprise_number)
                except Company.DoesNotExist:
                    continue  # Skip if no matching company found

            company = company_cache[enterprise_number]
            address_batch.append(Address(
                company=company,
                street=row['StreetNL'],
                house_number=row['HouseNumber'],
                postal_code=row['Zipcode'],
                city=row['MunicipalityNL'],
                country=row['CountryNL']
            ))

            if len(address_batch) >= batch_size:
                Address.objects.bulk_create(address_batch, batch_size=500)
                address_batch.clear()

        if address_batch:
            Address.objects.bulk_create(address_batch, batch_size=500)

        self.stdout.write(self.style.SUCCESS('🏠 Addresses loaded incrementally.'))