import os
import logging
import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from companies.models import Company, Address
from rapidfuzz import fuzz
import hashlib
import copy
import json
import re

logger = logging.getLogger(__name__)

SUFFIX_PATTERN = r'\b(bvba|bv|nv|cvba|cv|vzw|sprl|srl|asbl|gmbh|sa|plc|ltd|llc)\b$'
FUZZY_MATCH_THRESHOLD = 80
CACHE_TIMEOUT = 3600  # seconds (1 hour)

DEV_CACHE_DIR = "dev_api_cache"
DEV_MODE = settings.DEBUG

os.makedirs(DEV_CACHE_DIR, exist_ok=True)

def parse_address_string(address_string):
    # Pre-clean: remove leading bus/unit if present
    cleaned_address = re.sub(r'^(bus|boîte|bte)\s*\d+\s*,\s*', '', address_string, flags=re.IGNORECASE)

    # Match street + house number (digits only), optionally followed by unit
    match = re.match(
        r'^(?P<street>.*?)\s*(?P<number>\d+[./]?\d*[a-zA-Z]?)\s*,?\s*(?P<postal_code>\d{4,5})\s+(?P<city>[A-Za-zÀ-ÿ\'\- ]+)',
        cleaned_address,
        re.IGNORECASE
    )

    if not match:
        return None, None, None, None

    street = match.group("street").strip()
    house_number = match.group("number").strip()  # Just the digits
    postal_code = match.group("postal_code").strip()
    city = match.group("city").strip()

    return street, house_number, postal_code, city


def normalize_name(name):
    name = name.lower().strip()
    name = re.sub(SUFFIX_PATTERN, '', name).strip()
    return name


def enrich_with_company_data(places_data):
    enriched = []

    for place in places_data:
        matched_company = None
        street, house_number, postal_code, city = parse_address_string(place.get("address", ""))
        name = normalize_name(place.get("name", ""))
        place_id = place.get("place_id")
        
        if place_id:
            matched_company = Company.objects.filter(maps_id=place_id).first()
        
        if matched_company is None:
            companies = Company.objects.filter(name__iexact=name)
            company = companies.first()
            if company and not companies[1:2].exists():  # ensures only one
                matched_company = company
            else:
                if street and postal_code and house_number and city:
                    possible_addresses = Address.objects.filter(
                        street=street,
                        postal_code=postal_code,
                        house_number=house_number,
                    ).select_related("company")
                    print('Possible addresses: ', possible_addresses)
                else:
                    possible_addresses = Address.objects.none()
                    
                if possible_addresses.count() == 1:
                    matched_company = possible_addresses.first().company
                
                elif possible_addresses.count() > 1:
                    best_score = 0   
                    for possible_address in possible_addresses:
                        company_name = normalize_name(possible_address.company.name)
                        if company_name == name:
                            matched_company = possible_address.company
                            break
                        
                        ratio = fuzz.WRatio(company_name, name)
                        if ratio > FUZZY_MATCH_THRESHOLD and ratio > best_score:
                            best_score = ratio
                            matched_company = possible_address.company
            
                
        result = {
            "company_name": matched_company.name if matched_company else None,
            "vat_number": matched_company.number if matched_company else None,
            "company_id": matched_company.id if matched_company else None,
        }
        
        if matched_company and matched_company.maps_id != place_id:
            Company.objects.filter(id=matched_company.id).update(maps_id=place_id)

        place.update(result)
        enriched.append(place)

    return enriched

def get_dev_cache_path(textQuery, nextPageToken=None):
    safe_text = re.sub(r'[^a-zA-Z0-9_-]', '_', textQuery)
    safe_token = re.sub(r'[^a-zA-Z0-9_-]', '_', nextPageToken) if nextPageToken else ''
    
    base_string = f"{safe_text}_{safe_token}" if nextPageToken else safe_text
    hashed = hashlib.md5(base_string.encode('utf-8')).hexdigest()
    
    return os.path.join(DEV_CACHE_DIR, f"{hashed}.json")

def GoogleMapsPlacesAPI(textQuery, nextPageToken=None):

    
    if DEV_MODE:
        dev_cache_path = get_dev_cache_path(textQuery, nextPageToken)
        if os.path.exists(dev_cache_path):
            with open(dev_cache_path, "r") as f:
                return json.load(f)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.websiteUri,nextPageToken"
    }

    if nextPageToken:
        payload = {
            "textQuery": textQuery,
            "locationRestriction": {
                "rectangle": {
                    "low": {"latitude": 51, "longitude": 2.5},
                    "high": {"latitude": 51.5, "longitude": 6}
                }
            },
            "pageToken": nextPageToken
        }
    else:
        payload = {
            "textQuery": textQuery,
            "locationRestriction": {
                "rectangle": {
                    "low": {"latitude": 51, "longitude": 2.5},
                    "high": {"latitude": 51.5, "longitude": 6}
                }
            }
        }

    try:
        response = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {e}")

    places = []
    for place in data.get("places", []):
        places.append({
            'place_id': place.get('id'),
            'name': place.get('displayName', {}).get('text'),
            'address': place.get('formattedAddress'),
            'website': place.get('websiteUri'),
            'vat_number': None,
            'company_id': None,
        })

    filtered_data = {
        "places": places,
        "nextPageToken": data.get("nextPageToken"),
    }

    if DEV_MODE:
        with open(get_dev_cache_path(textQuery, nextPageToken), "w") as f:
            json.dump(filtered_data, f, indent=2)

    return filtered_data