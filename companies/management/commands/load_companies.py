import csv
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from companies.models import Company, Address
from companies.utils import parse_enterprise_number


class Command(BaseCommand):
    help = 'Load companies from CSV files (enterprise, denomination, addresses)'

    def handle(self, *args, **options):
        self.load_companies('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/enterprise.csv')
        self.load_denomination('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/denomination.csv')
        
        address_urls = [
            'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address_part_1.csv',
            'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address_part_2.csv',
            'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address_part_3.csv',
            'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address_part_4.csv',
            'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address_part_5.csv',
            'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address_part_6.csv',
        ]
        for urls in address_urls:
            self.load_addresses(urls)
            
        self.update_legal_forms('https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/enterprise.csv')

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
            enterprise_number = parse_enterprise_number(row['EnterpriseNumber'])
            if enterprise_number not in existing_numbers:
                new_companies.append(Company(
                    number=enterprise_number,
                    status_code=row['JuridicalSituation'],
                    enterprise_type_code=row['TypeOfEnterprise'],
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
            enterprise_number = parse_enterprise_number(row['EntityNumber'])
            denom_batch[enterprise_number] = row['Denomination']

            if len(denom_batch) >= batch_size:
                amount = self._update_company_names(denom_batch)
                count += amount
                denom_batch.clear()
                

        if denom_batch:
            amount = self._update_company_names(denom_batch)
            count += amount

        self.stdout.write(self.style.SUCCESS(f'📝 {count} Denominations updated incrementally.'))

    def _update_company_names(self, denom_map):
        count = 0
        companies = Company.objects.filter(number__in=denom_map.keys())
        companies_to_update = []
        for company in companies:
            new_name = denom_map.get(company.number)
            if new_name and not company.name:
                company.name = new_name
                companies_to_update.append(company)
                count += 1

        if companies_to_update:
            Company.objects.bulk_update(companies_to_update, ['name'], batch_size=500)
        
        return count

    def load_addresses(self, url):
        batch_size = 500
        address_batch = []
        count = 0

        existing_company_ids = set(Address.objects.values_list('company_id', flat=True))
        company_map = dict(Company.objects.values_list('number', 'id'))

        for row in self.stream_csv(url, delimiter=';'):
            enterprise_number = parse_enterprise_number(row['EntityNumber'])
            company_id = company_map.get(enterprise_number)

            if not company_id:
                continue  # No matching company

            if company_id in existing_company_ids:
                continue  # Address already exists for this company

            count += 1
            address_batch.append(Address(
                company_id=company_id,  # Use foreign key ID directly for faster instantiation
                type=row['TypeOfAddress'],
                street=row['Street'],
                house_number=row['HouseNumber'],
                postal_code=row['Zipcode'],
                city=row['Municipality'],
            ))

            if len(address_batch) >= batch_size:
                Address.objects.bulk_create(address_batch, batch_size=batch_size)
                existing_company_ids.update(a.company_id for a in address_batch)
                address_batch.clear()

        if address_batch:
            Address.objects.bulk_create(address_batch, batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS(f'🏠 {count} addresses loaded incrementally.'))
        
    def update_legal_forms(self, url):
        number_to_legalform = {}

        # Step 1: Collect legal forms from the CSV
        for row in self.stream_csv(url, delimiter=';'):
            number = parse_enterprise_number(row['EnterpriseNumber'])
            legal_form = row.get('JuridicalForm')
            if number and legal_form:
                number_to_legalform[number] = legal_form

        # Step 2: Only fetch companies that are in the CSV
        companies = Company.objects.filter(number__in=number_to_legalform.keys()).only("id", "number", "legalform_code")

        companies_to_update = []
        count = 0
        batch_size = 500

        # Step 3: Update only if field is empty
        for company in companies:
            legal_form = number_to_legalform[company.number]
            if not company.legalform_code:
                company.legalform_code = legal_form
                companies_to_update.append(company)
                count += 1

            if len(companies_to_update) >= batch_size:
                Company.objects.bulk_update(companies_to_update, ['legalform_code'], batch_size=batch_size)
                companies_to_update.clear()

        if companies_to_update:
            Company.objects.bulk_update(companies_to_update, ['legalform_code'], batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS(f'🧩 {count} legal forms updated.'))