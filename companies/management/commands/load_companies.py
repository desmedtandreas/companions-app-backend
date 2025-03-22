import pandas as pd
import requests
from io import StringIO
from django.core.management.base import BaseCommand
from companies.models import Company, Address

class Command(BaseCommand):
    help = 'Load companies from CSV files (enterprise, denomination, addresses)'

    def handle(self, *args, **options):
        companies_url = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/enterprise.csv'
        denomination_url = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/denomination.csv'
        addresses_url = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address.csv'

        self.load_companies(companies_url)
        self.load_denomination(denomination_url)
        self.load_addresses(addresses_url)

        self.stdout.write(self.style.SUCCESS('✅ Successfully loaded companies and addresses.'))

    def download_csv(self, url):
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text), low_memory=False)

    def load_companies(self, url):
        df = self.download_csv(url)
        df = df[df['TypeOfEnterprise'] == 2]

        existing_numbers = set(Company.objects.values_list('enterprise_number', flat=True))
        new_companies = [
            Company(enterprise_number=row['EnterpriseNumber'], legal_form=row['JuridicalForm'])
            for _, row in df.iterrows()
            if row['EnterpriseNumber'] not in existing_numbers
        ]

        Company.objects.bulk_create(new_companies, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f'🚀 Created {len(new_companies)} new companies.'))

    def load_denomination(self, url):
        df = self.download_csv(url)
        df = df[df['TypeOfDenomination'] == '001']

        denom_map = dict(zip(df['EntityNumber'], df['Denomination']))

        companies = list(Company.objects.filter(enterprise_number__in=denom_map.keys()))

        companies_to_update = []
        for company in companies:
            new_name = denom_map.get(company.enterprise_number)
            if new_name and not company.name:
                company.name = new_name
                companies_to_update.append(company)

        Company.objects.bulk_update(companies_to_update, ['name'], batch_size=1000)
        self.stdout.write(self.style.SUCCESS(
            f'📝 Updated names for {len(companies_to_update)} companies.'
        ))

    def load_addresses(self, url):
        df = self.download_csv(url)

        companies = {
            c.enterprise_number: c
            for c in Company.objects.all()
        }

        addresses = []
        for _, row in df.iterrows():
            company = companies.get(row['EntityNumber'])
            if company:
                addresses.append(Address(
                    company=company,
                    street=row['StreetNL'],
                    house_number=row['HouseNumber'],
                    postal_code=row['Zipcode'],
                    city=row['MunicipalityNL'],
                    country=row['CountryNL']
                ))

        Address.objects.bulk_create(addresses, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f'🏠 Created {len(addresses)} addresses.'))