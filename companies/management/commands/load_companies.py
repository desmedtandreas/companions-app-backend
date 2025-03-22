import csv
from collections import defaultdict
from django.core.management.base import BaseCommand
from companies.models import Company, Address
from django.db import transaction

class Command(BaseCommand):
    help = 'Load companies from CSV files (enterprise, denomination, addresses)'

    def handle(self, *args, **options):
        self.load_companies('https://drive.google.com/uc?export=download&id=19O_bGf_Os0lLa7T9ZKrkq1sNX1hrMdfR')
        self.load_denomination('https://drive.google.com/uc?export=download&id=1XmGL7urCXwzYgLGvreyGFCo3c6YNv9Pe')
        self.load_addresses('https://drive.google.com/uc?export=download&id=1guWNR7v-Hl94cYy62t3n2HQWC_fjHAbc')
        self.stdout.write(self.style.SUCCESS('✅ Successfully loaded companies and addresses.'))

    def load_companies(self, path):
        with open(path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            enterprise_numbers = set()
            new_companies = []

            existing = set(Company.objects.values_list('enterprise_number', flat=True))

            for row in reader:
                if row['TypeOfEnterprise'] != '2':
                    continue

                enterprise_number = row['EnterpriseNumber']
                enterprise_numbers.add(enterprise_number)

                if enterprise_number not in existing:
                    new_companies.append(Company(
                        enterprise_number=enterprise_number,
                        legal_form=row['JuridicalForm']
                    ))

            Company.objects.bulk_create(new_companies, batch_size=1000)
            self.stdout.write(self.style.SUCCESS(f'🚀 Created {len(new_companies)} new companies.'))

    def load_denomination(self, path):
        with open(path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            names = {}

            for row in reader:
                if row['TypeOfDenomination'] != '001':
                    continue
                names[row['EntityNumber']] = row['Denomination']

        def chunked(iterable, size):
            for i in range(0, len(iterable), size):
                yield iterable[i:i+size]

        enterprise_numbers = list(names.keys())
        companies = []

        for chunk in chunked(enterprise_numbers, 900):  # 500 is safe for SQLite
            companies += list(Company.objects.filter(enterprise_number__in=chunk))

        companies_to_update = []
        for company in companies:
            if not company.name:
                new_name = names.get(company.enterprise_number)
                if new_name:
                    company.name = new_name
                    companies_to_update.append(company)

        Company.objects.bulk_update(companies_to_update, ['name'], batch_size=1000)
        self.stdout.write(self.style.SUCCESS(
            f'📝 Updated names for {len(companies_to_update)} companies.'
        ))

    def load_addresses(self, path):
        with open(path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            addresses = []
            company_map = {
                c.enterprise_number: c
                for c in Company.objects.all()
            }

            for row in reader:
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

            Address.objects.bulk_create(addresses, batch_size=1000)
            self.stdout.write(self.style.SUCCESS(f'🏠 Created {len(addresses)} addresses.'))