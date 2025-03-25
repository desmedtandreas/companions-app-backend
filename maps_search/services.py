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
import time

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
    
    start = time.time()
    # 1. Pre-fetch companies by maps_id
    place_ids = {place.get("place_id") for place in places_data if place.get("place_id")}
    companies_by_maps_id = {
        company.maps_id: company
        for company in Company.objects.filter(maps_id__in=place_ids)
    }
    print("Pre-fetching companies took", time.time() - start, "seconds")
    
    # 2. Pre-fetch companies by normalized name using Q objects
    normalized_names = {
        normalize_name(place.get("name", ""))
        for place in places_data 
        if not (place.get("place_id") and place.get("place_id") in companies_by_maps_id)
    }
    
    q_objects = Q()
    for name in normalized_names:
        q_objects |= Q(name__iexact=name)
    
    companies_by_name_qs = Company.objects.filter(q_objects)
    
    # Map normalized names to companies
    companies_by_normalized_name = {}
    for company in companies_by_name_qs:
        norm_name = normalize_name(company.name)
        companies_by_normalized_name.setdefault(norm_name, []).append(company)
    
    # Only keep unique matches (i.e. exactly one company for a normalized name)
    unique_company_by_name = {
        name: comps[0] for name, comps in companies_by_normalized_name.items() if len(comps) == 1
    }
    
    # 3. Bulk-fetch addresses:
    # Collect unique address keys from places with valid address info.
    address_keys = set()
    for place in places_data:
        street, house_number, postal_code, city = parse_address_string(place.get("address", ""))
        if street and postal_code and house_number and city:
            address_keys.add((street, postal_code, house_number))
            
    # Build a Q object to fetch all addresses for these keys.
    addr_q = Q()
    for key in address_keys:
        street, postal_code, house_number = key
        addr_q |= Q(street=street, postal_code=postal_code, house_number=house_number)
    addresses = Address.objects.filter(addr_q).select_related("company") if addr_q else []
    
    # Group addresses by (street, postal_code, house_number)
    addresses_by_key = {}
    for addr in addresses:
        key = (addr.street, addr.postal_code, addr.house_number)
        addresses_by_key.setdefault(key, []).append(addr)
    
    # 4. Process each place and collect maps_id updates
    maps_id_updates = []  # to batch update maps_id later
    enriched = []
    
    start = time.time()
    for place in places_data:
        matched_company = None
        street, house_number, postal_code, city = parse_address_string(place.get("address", ""))
        norm_name = normalize_name(place.get("name", ""))
        place_id = place.get("place_id")
        
        # Try matching by maps_id first.
        if place_id and place_id in companies_by_maps_id:
            matched_company = companies_by_maps_id[place_id]
        # Then try unique company by normalized name.
        elif norm_name in unique_company_by_name:
            matched_company = unique_company_by_name[norm_name]
        # Finally, try matching via address.
        elif street and postal_code and house_number and city:
            key = (street, postal_code, house_number)
            possible_addresses = addresses_by_key.get(key, [])
            
            if len(possible_addresses) == 1:
                matched_company = possible_addresses[0].company
            elif len(possible_addresses) > 1:
                best_score = 0
                for possible_address in possible_addresses:
                    company_name = normalize_name(possible_address.company.name)
                    # If names match exactly, break early.
                    if company_name == norm_name:
                        matched_company = possible_address.company
                        break
                    ratio = fuzz.WRatio(company_name, norm_name)
                    if ratio > FUZZY_MATCH_THRESHOLD and ratio > best_score:
                        best_score = ratio
                        matched_company = possible_address.company
        
        result = {
            "company_name": matched_company.name if matched_company else None,
            "vat_number": matched_company.number if matched_company else None,
            "company_id": matched_company.id if matched_company else None,
        }
        if matched_company and matched_company.maps_id != place_id:
            maps_id_updates.append((matched_company.id, place_id))
        
        place.update(result)
        enriched.append(place)
    
    # 5. Batch update maps_id for companies where needed.
    for company_id, new_maps_id in maps_id_updates:
        Company.objects.filter(id=company_id).update(maps_id=new_maps_id)
    
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
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.websiteUri"
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
            'place_id': place.get('id'),
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