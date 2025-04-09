import tempfile
import requests
import csv
from django.core.management.base import BaseCommand
from companies.models import CodeLabel


class Command(BaseCommand):
    help = 'Load codes into the database'

    def handle(self, *args, **options):
        csv_path = 'https://github.com/desmedtandreas/companions-app-backend/releases/download/company_data/code.csv'
        
        self.load_codes(csv_path)
        
        self.stdout.write(self.style.SUCCESS('✅ Successfully loaded all data.'))

    def load_codes(self, csv_url):
        try:
            self.stdout.write(f"📥 Downloading CSV from: {csv_url}")
            response = requests.get(csv_url)
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, mode='wb') as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
            self.stdout.write(f"📄 CSV temporarily saved at: {temp_file_path}")

            with open(temp_file_path, mode='r', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)
                row_count = 0
                processed = 0
                skipped = 0

                for row in reader:
                    row_count += 1
                    category = row.get('Category')
                    language = row.get('Language')
                    code = row.get('Code')
                    description = row.get('Description')

                    if not category or not code or not description:
                        self.stdout.write(self.style.WARNING(f"⚠️ Skipped row {row_count}: missing required fields"))
                        skipped += 1
                        continue

                    if language == 'NL':
                        CodeLabel.objects.update_or_create(
                            code=code,
                            category=category,
                            defaults={'name': description}
                        )
                        self.stdout.write(self.style.SUCCESS(f"✔ Row {row_count}: {code} → {description}"))
                        processed += 1
                    else:
                        skipped += 1

                amount = CodeLabel.objects.count()
                self.stdout.write(self.style.SUCCESS(f"✅ Processed: {processed} row(s), Skipped: {skipped}"))
                self.stdout.write(self.style.SUCCESS(f"Total records in CodeLabel: {amount}"))
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"❌ Error downloading the file: {e}"))
        except csv.Error as e:
            self.stderr.write(self.style.ERROR(f"❌ Error reading the CSV file: {e}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Unexpected error: {e}"))