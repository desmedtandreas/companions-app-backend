import requests 
import json
import uuid
from django.conf import settings
from .utils import parse_enterprise_number


def get_references(enterprise_number):
    
    enterprise_number = parse_enterprise_number(enterprise_number)
    
    headers = {
        'NBB-CBSO-Subscription-Key': '47b03c68108943a78ad42959e839b1f8',
        'X-Request-Id': str(uuid.uuid4()),
        'Accept': 'application/json',
        'User-Agent': 'curl/7.81.0'
    }
    
    url = f'https://ws.cbso.nbb.be/authentic/legalEntity/{enterprise_number}/references'
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        if response.status_code == 404:
            return {}
        else:
            raise e

    return data
    
    
def get_accounting_data(reference_number):
    
    headers = {
        'NBB-CBSO-Subscription-Key': '47b03c68108943a78ad42959e839b1f8',
        'X-Request-Id': str(uuid.uuid4()),
        'Accept': 'application/x.jsonxbrl',
        'User-Agent': 'curl/7.81.0'
    }
    
    url = f'https://ws.cbso.nbb.be/authentic/deposit/{reference_number}/accountingData'
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        if response.status_code == 404:
            return {}
        else:
            raise e

    return data
        