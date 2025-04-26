import csv
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from companies.models import Company, Address
from companies.utils import parse_enterprise_number
from itertools import islice


class Command(BaseCommand):
    help = 'Load or update companies, addresses, and legal forms from CSV files.'

    ENTERPRISE_URL = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/enterprise.csv'
    DENOMINATION_URL = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/denomination.csv'
    ADDRESS_URLS = [
        f'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/address_part_{i}.csv' for i in range(1, 7)
    ]

    def handle(self, *args, **options):
        self.load_companies(self.ENTERPRISE_URL)
        self.load_denomination(self.DENOMINATION_URL)
        for url in self.ADDRESS_URLS:
            self.load_addresses(url)
        self.update_legal_forms(self.ENTERPRISE_URL)
        self.stdout.write(self.style.SUCCESS('✅ Successfully loaded and updated all data.'))

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
        """
        Batch-load companies from CSV by chunks to minimize memory and DB hits.
        """

        created = 0
        updated = 0
        skipped = 0
        processed_rows = 0
        batch_size = 5000

        def chunked(iterator, size):
            while True:
                chunk = list(islice(iterator, size))
                if not chunk:
                    break
                yield chunk

        rows_iter = self.stream_csv(url)
        for batch in chunked(rows_iter, batch_size):
            to_create = []
            to_update = []
            numbers = []
            row_map = []

            # Parse and filter rows
            for row in batch:
                number = parse_enterprise_number(row['EnterpriseNumber'])
                raw_start = row.get('StartDate', '')
                date_val = self.parse_date(raw_start)
                if not number or not date_val:
                    skipped += 1
                    continue
                numbers.append(number)
                row_map.append((number, date_val, row.get('JuridicalSituation'), row.get('TypeOfEnterprise')))

            # Fetch existing companies in one query
            existing_qs = Company.objects.filter(number__in=numbers).only(
                'number', 'start_date', 'status_code', 'enterprise_type_code')
            existing = {c.number: c for c in existing_qs}

            # Prepare create/update lists
            for number, date_val, status, etype in row_map:
                if number in existing:
                    comp = existing[number]
                    comp.start_date = date_val
                    comp.status_code = status or comp.status_code
                    comp.enterprise_type_code = etype or comp.enterprise_type_code
                    to_update.append(comp)
                    updated += 1
                else:
                    to_create.append(Company(
                        number=number,
                        start_date=date_val,
                        status_code=status or '',
                        enterprise_type_code=etype or ''
                    ))
                    created += 1

            # Bulk write
            if to_create:
                Company.objects.bulk_create(to_create, batch_size=batch_size)
            if to_update:
                Company.objects.bulk_update(to_update,
                    ['start_date', 'status_code', 'enterprise_type_code'],
                    batch_size=batch_size
                )

            processed_rows += len(batch)
            self.stdout.write(
                f"Processed {processed_rows} rows so far (created: {created}, updated: {updated}, skipped: {skipped})"
            )

        # Final summary
        self.stdout.write(self.style.SUCCESS(
            f"🏢 Total companies: {created} created, {updated} updated, {skipped} skipped."
        ))

    def load_denomination(self, url):
        """
        Batch-update company denominations from CSV in chunks for speed.
        """

        batch_size = 5000
        updated_count = 0
        skipped_count = 0
        unchanged_count = 0
        processed_rows = 0

        def chunked(iterator, size):
            while True:
                chunk = list(islice(iterator, size))
                if not chunk:
                    break
                yield chunk

        rows_iter = self.stream_csv(url)
        for batch in chunked(rows_iter, batch_size):
            numbers = []
            row_map = []
            batch_processed = 0

            # Parse and filter rows
            for row in batch:
                batch_processed += 1
                processed_rows += 1
                number = parse_enterprise_number(row.get('EntityNumber', ''))
                denom = row.get('Denomination')
                if not number or not denom:
                    skipped_count += 1
                    continue
                numbers.append(number)
                row_map.append((number, denom))

            # Fetch existing companies in bulk
            existing_qs = Company.objects.filter(number__in=numbers).only('number', 'name')
            existing = {c.number: c for c in existing_qs}

            to_update = []
            for number, denom in row_map:
                comp = existing.get(number)
                if comp:
                    if comp.name != denom:
                        comp.name = denom
                        to_update.append(comp)
                        updated_count += 1
                    else:
                        unchanged_count += 1
                else:
                    skipped_count += 1

            # Bulk-update names
            if to_update:
                Company.objects.bulk_update(to_update, ['name'], batch_size=batch_size)

            self.stdout.write(
                f"Processed batch of {batch_processed} denominations (total processed: {processed_rows}). "  \
                f"Updated: {updated_count}, Skipped: {skipped_count}, Unchanged: {unchanged_count}."
            )

        # Final summary
        self.stdout.write(self.style.SUCCESS(
            f"📝 Total processed: {processed_rows}. {updated_count} updated, {skipped_count} skipped, {unchanged_count} unchanged."
        ))

    def load_addresses(self, url):
        """
        Batch-load addresses from CSV by chunks to minimize DB hits and speed.
        """
        from itertools import islice

        batch_size = 5000
        created_count = 0
        updated_count = 0
        skipped_count = 0
        processed_rows = 0

        def chunked(iterator, size):
            while True:
                chunk = list(islice(iterator, size))
                if not chunk:
                    break
                yield chunk

        rows_iter = self.stream_csv(url)
        for batch in chunked(rows_iter, batch_size):
            # Parse batch and collect company numbers and address types
            row_map = []  # list of (company_number, type, street, house_number, postal_code, city)
            numbers = set()
            types = set()
            batch_processed = 0
            for row in batch:
                batch_processed += 1
                processed_rows += 1
                number = parse_enterprise_number(row.get('EntityNumber', ''))
                addr_type = row.get('TypeOfAddress')
                if not number or not addr_type:
                    skipped_count += 1
                    continue
                row_map.append((number, addr_type,
                                row.get('Street'),
                                row.get('HouseNumber'),
                                row.get('Zipcode'),
                                row.get('Municipality')))
                numbers.add(number)
                types.add(addr_type)

            # Map company numbers to IDs
            companies = Company.objects.filter(number__in=numbers).only('id', 'number')
            company_map = {c.number: c.id for c in companies}

            # Determine existing addresses
            # Key by (company_id, type)
            existing_qs = Address.objects.filter(
                company_id__in=company_map.values(),
                type__in=types
            ).only('company_id', 'type', 'street', 'house_number', 'postal_code', 'city')
            existing_keys = {(a.company_id, a.type): a for a in existing_qs}

            to_create = []
            to_update = []

            for number, addr_type, street, house_number, postal_code, city in row_map:
                comp_id = company_map.get(number)
                if not comp_id:
                    skipped_count += 1
                    continue
                key = (comp_id, addr_type)
                if key in existing_keys:
                    addr = existing_keys[key]
                    # check if any field changed
                    if (addr.street != street or addr.house_number != house_number or
                        addr.postal_code != postal_code or addr.city != city):
                        addr.street = street
                        addr.house_number = house_number
                        addr.postal_code = postal_code
                        addr.city = city
                        to_update.append(addr)
                        updated_count += 1
                    else:
                        # unchanged
                        pass
                else:
                    to_create.append(Address(
                        company_id=comp_id,
                        type=addr_type,
                        street=street,
                        house_number=house_number,
                        postal_code=postal_code,
                        city=city
                    ))
                    created_count += 1

            # Bulk operations
            if to_create:
                Address.objects.bulk_create(to_create, batch_size=batch_size)
            if to_update:
                Address.objects.bulk_update(
                    to_update,
                    ['street', 'house_number', 'postal_code', 'city'],
                    batch_size=batch_size
                )

            self.stdout.write(
                f"Processed batch of {batch_processed} addresses (total processed: {processed_rows}). "  \
                f"Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}."
            )

        # Final summary
        self.stdout.write(self.style.SUCCESS(
            f"🏠 Total addresses: {created_count} created, {updated_count} updated, {skipped_count} skipped (invalid or missing company)."
        ))

    def update_legal_forms(self, url):
        updated_count = 0
        processed = 0

        for row in self.stream_csv(url):
            number = parse_enterprise_number(row['EnterpriseNumber'])
            legal_form = row.get('JuridicalForm')

            if not number or not legal_form:
                continue

            company, created = Company.objects.update_or_create(
                number=number,
                defaults={
                    'legalform_code': legal_form,
                }
            )

            if not created:
                updated_count += 1

            processed += 1
            if processed % 1000 == 0:
                self.stdout.write(f'Processed {processed} legal forms...')

        self.stdout.write(self.style.SUCCESS(f'🧩 {updated_count} legal forms updated.'))