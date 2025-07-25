import csv
import io
import requests
from django.core.management.base import BaseCommand
from lists.models import Municipality  # or your actual model path
from urllib.parse import urlparse

class Command(BaseCommand):
    help = "Load Flemish municipalities from a CSV file or URL"

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the municipalities CSV file or a URL'
        )

    def handle(self, *args, **options):
        path = options['csv_file']

        # Determine if path is a URL
        is_url = urlparse(path).scheme in ('http', 'https')

        try:
            if is_url:
                self.stdout.write(f"Fetching CSV from URL: {path}")
                response = requests.get(path)
                response.raise_for_status()
                csvfile = io.StringIO(response.content.decode('utf-8'))
            else:
                self.stdout.write(f"Opening local file: {path}")
                csvfile = open(path, newline='', encoding='utf-8')

            reader = csv.DictReader(csvfile, delimiter=';', fieldnames=['NIS', 'Gemeente', 'Postcode'])
            next(reader)  # Skip header row inside the file

            count = 0
            for row in reader:
                nis = row['NIS'].zfill(5)
                name = row['Gemeente'].strip()

                _, created = Municipality.objects.update_or_create(
                    code=nis,
                    defaults={'name': name}
                )
                if created:
                    count += 1

            self.stdout.write(self.style.SUCCESS(f"{count} municipalities created or updated."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to load CSV: {e}"))
        finally:
            if not is_url:
                csvfile.close()
