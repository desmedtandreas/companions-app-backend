import csv
import requests
from tempfile import NamedTemporaryFile
from django.core.management.base import BaseCommand
from companies.models import Company, Address

class Command(BaseCommand):
    help = 'Load companies from CSV files (enterprise, denomination, addresses)'

    def handle(self, *args, **options):
        companies_url = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/enterprise.csv'
        denomination_url = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/denomination.csv'
        addresses_url = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address.csv'

        self.stdout.write("⏳ Starting companies load...")
        self.load_companies(companies_url)

        self.stdout.write("⏳ Starting denomination load...")
        self.load_denomination(denomination_url)

        self.stdout.write("⏳ Starting addresses load...")
        self.load_addresses(addresses_url)

        self.stdout.write(self.style.SUCCESS('✅ Successfully loaded all data.'))

    def stream_csv(self, url):
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            with NamedTemporaryFile(mode='w+', newline='', delete=True) as tmp:
                for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                    tmp.write(chunk)
                tmp.flush()
                tmp.seek(0)
                reader = csv.DictReader(tmp)
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

            if len(new_companies) >= 1000:
                Company.objects.bulk_create(new_companies, batch_size=1000)
                new_companies.clear()

        if new_companies:
            Company.objects.bulk_create(new_companies, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f'🚀 Created new companies.'))

    def load_denomination(self, url):
        denom_map = {}
        for row in self.stream_csv(url):
            if row['TypeOfDenomination'] == '001':
                denom_map[row['EntityNumber']] = row['Denomination']

        companies = Company.objects.filter(enterprise_number__in=denom_map.keys())

        companies_to_update = []
        for company in companies:
            new_name = denom_map.get(company.enterprise_number)
            if new_name and not company.name:
                company.name = new_name
                companies_to_update.append(company)

        Company.objects.bulk_update(companies_to_update, ['name'], batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f'📝 Updated names for {len(companies_to_update)} companies.'))

    def load_addresses(self, url):
        company_map = {c.enterprise_number: c for c in Company.objects.all()}
        addresses = []

        for row in self.stream_csv(url):
            company = company_map.get(row['EntityNumber'])
            if company:
                addresses.append(Address(
                    company=company,
                    street=row['StreetNL'],
                    house_number=row['HouseNumber'],
                    postal_code=row['Zipcode'],
                    city=row['MunicipalityNL'],
                    country=row['CountryNL']
                ))

            if len(addresses) >= 1000:
                Address.objects.bulk_create(addresses, batch_size=1000)
                addresses.clear()

        if addresses:
            Address.objects.bulk_create(addresses, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f'🏠 Created new addresses.'))