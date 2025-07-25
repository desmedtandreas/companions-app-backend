import csv
from django.core.management.base import BaseCommand
from lists.models import Municipality  # Replace with your actual app name

class Command(BaseCommand):
    help = "Load Flemish municipalities from CSV"

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the municipalities CSV file')

    def handle(self, *args, **options):
        path = options['csv_file']
        with open(path, newline='', encoding='utf-8') as csvfile:
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