import boto3
import os
import io
import csv
from datetime import datetime
import re

from .utils import parse_enterprise_number
from .models import Company, Address

def remove_parentheses(text):
    if not text:
        return ""
    return re.sub(r"\s*\(.*?\)", "", text).strip()

def parse_date(date_str):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            return datetime.now().date()

def import_kbo_open_data(s3_prefix):
    print(f"Loading KBO data from S3 prefix: {s3_prefix}")

    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
    )

    bucket_name = os.getenv("S3_BUCKET_NAME")

    # List all files under the given prefix
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_prefix)

    if 'Contents' not in response:
        print("No files found.")
        return

    # Map filenames to their S3 key (full path)
    available_files = {obj['Key'].split("/")[-1]: obj['Key'] for obj in response['Contents']}

    # Define correct processing order
    files_in_order = [
        "enterprise_insert.csv",
        "enterprise_delete.csv",
        "denomination_insert.csv",
        "address_insert.csv",
    ]

    for filename in files_in_order:
        if filename not in available_files:
            print(f"Skipping {filename} (not found).")
            continue

        key = available_files[filename]
        print(f"Processing file: {filename}")

        s3_object = s3.get_object(Bucket=bucket_name, Key=key)
        file_content = s3_object['Body'].read()

        csv_file = io.StringIO(file_content.decode('utf-8'))
        reader = csv.DictReader(csv_file)

        if filename == "enterprise_insert.csv":
            update_create_companies(reader)
        elif filename == "enterprise_delete.csv":
            deactivate_companies(reader)
        elif filename == "denomination_insert.csv":
            update_denomination(reader)
        elif filename == "address_insert.csv":
            update_create_addresses(reader)

            

def update_create_companies(reader):
    print("Updating/Creating companies...")
    for row in reader:
        if row['TypeOfEnterprise'] != "0" and row['TypeOfEnterprise'] != "2":
            continue
        enterprise_number = parse_enterprise_number(row['EnterpriseNumber'])
        company, created = Company.objects.update_or_create(
            number=enterprise_number,
            defaults={
            'status_code': row['JuridicalSituation'],
            'enterprise_type_code': row['TypeOfEnterprise'],
            'start_date': parse_date(row['StartDate']),
            }
        )
        if created:
            print(f"Created new company: {company.name}")
        else:
            print(f"Updated existing company: {company.name}")
    print("Companies updated/created.")
    
def deactivate_companies(reader):
    print("Deactivating companies...")
    for row in reader:
        enterprise_number = parse_enterprise_number(row['EnterpriseNumber'])
        try:
            company = Company.objects.get(number=enterprise_number)
            company.status_code = "0"
            company.save()
        except Company.DoesNotExist:
            print(f"Company with number {enterprise_number} does not exist.")
    print("Companies deactivated.")
    
def update_denomination(reader):
    print("Updating denominations...")
    for row in reader:
        if row['TypeOfDenomination'] != "001":
            continue
        enterprise_number = parse_enterprise_number(row['EntityNumber'])
        try:
            company = Company.objects.get(number=enterprise_number)
            company.name = row['Denomination']
            company.save()
            print(f"Updated denomination for {company.name}")
        except Company.DoesNotExist:
            print(f"Company with number {enterprise_number} does not exist.")
    print("Denominations updated.")
    
def update_create_addresses(reader):
    print("Updating/Creating addresses...")
    for row in reader:
        enterprise_number = parse_enterprise_number(row['EntityNumber'])
        try:
            company = Company.objects.get(number=enterprise_number)
        except Company.DoesNotExist:
            continue

        address, created = Address.objects.update_or_create(
            company=company,
            type=row['TypeOfAddress'],   # These are the lookup fields
            defaults={                   # These fields will be updated or used when creating
                'street': remove_parentheses(row['StreetNL']),
                'house_number': row['HouseNumber'],
                'postal_code': row['Zipcode'],
                'city': remove_parentheses(row['MunicipalityNL']),
            }
        )
        if created:
            print(f"Created new address for {company.name}: {address}")
        else:
            print(f"Updated existing address for {company.name}: {address}")
    print("Addresses updated/created.")