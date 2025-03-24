import os
import logging
import requests
from django.conf import settings
from django.core.cache import cache
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

        normalized_key = f"{name}_{street}_{house_number}_{postal_code}"
        cache_key = f"enriched_place:{hashlib.md5(normalized_key.encode()).hexdigest()}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            # Deep copy to avoid mutations
            place.update(copy.deepcopy(cached_result))
            enriched.append(place)
            continue

        if street and postal_code and house_number and city:
            print('Address: ', street, house_number, postal_code, city)
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
                    
        else:
            companies = Company.objects.filter(name__iexact=name)
            if companies.count() == 1:
                matched_company = companies.first()
            
                
        result = {
            "company_name": matched_company.name if matched_company else None,
            "vat_number": matched_company.number if matched_company else None,
            "company_id": matched_company.id if matched_company else None,
        }

        cache.set(cache_key, copy.deepcopy(result), CACHE_TIMEOUT)

        place.update(result)
        enriched.append(place)

    return enriched

def get_dev_cache_path(textQuery):
    hashed = hashlib.md5(textQuery.encode()).hexdigest()
    return os.path.join(DEV_CACHE_DIR, f"{hashed}.json")

def GoogleMapsPlacesAPI(textQuery):
    cache_key = f"google_places:{hashlib.md5(textQuery.encode()).hexdigest()}"
    
    if DEV_MODE:
        dev_cache_path = get_dev_cache_path(textQuery)
        if os.path.exists(dev_cache_path):
            with open(dev_cache_path, "r") as f:
                return json.load(f)
    
    cached_response = cache.get(cache_key)
    if cached_response:
        # Deep copy to avoid mutations
        return copy.deepcopy(cached_response)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.websiteUri"
    }

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

    filtered_data = []
    for place in data.get("places", []):
        filtered_data.append({
            'name': place.get('displayName', {}).get('text'),
            'address': place.get('formattedAddress'),
            'website': place.get('websiteUri'),
            'vat_number': None,
            'company_id': None,
        })

    # Store a deep copy in cache to avoid future mutations
    cache.set(cache_key, copy.deepcopy(filtered_data), CACHE_TIMEOUT)
    
    if DEV_MODE:
        with open(get_dev_cache_path(textQuery), "w") as f:
            json.dump(filtered_data, f, indent=2)

    return filtered_data