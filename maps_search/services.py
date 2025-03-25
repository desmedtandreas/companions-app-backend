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

def get_preloaded_companies():
    companies_dict = cache.get("companies_by_name")

    if not companies_dict:
        print("⏳ Preloading companies...")
        companies_dict = {}
        for company in Company.objects.only("id", "name", "number", "maps_id").iterator():
            normalized = normalize_name(company.name)
            companies_dict[normalized] = {
                "id": company.id,
                "name": company.name,
                "number": company.number,
                "maps_id": company.maps_id,
            }
        cache.set("companies_by_name", companies_dict, timeout=86400)  # 1 day cache

    return companies_dict

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
    companies_by_name = get_preloaded_companies()

    for place in places_data:
        matched_company = None
        street, house_number, postal_code, city = parse_address_string(place.get("address", ""))
        name = normalize_name(place.get("name", ""))
        place_id = place.get("place_id")

        # 1. Match by maps_id
        if place_id:
            db_match = Company.objects.filter(maps_id=place_id).only("id", "name", "number", "maps_id").first()
            if db_match:
                matched_company = {
                    "id": db_match.id,
                    "name": db_match.name,
                    "number": db_match.number,
                    "maps_id": db_match.maps_id,
                }

        # 2. Match by normalized name from cache
        if not matched_company:
            matched_company = companies_by_name.get(name)

        # 3. Address-based fallback (if still no match)
        if not matched_company and street and postal_code and house_number and city:
            possible_addresses = Address.objects.filter(
                street=street,
                postal_code=postal_code,
                house_number=house_number,
            ).select_related("company")

            if possible_addresses.count() == 1:
                company = possible_addresses.first().company
                matched_company = {
                    "id": company.id,
                    "name": company.name,
                    "number": company.number,
                    "maps_id": company.maps_id,
                }

            elif possible_addresses.count() > 1:
                best_score = 0
                for addr in possible_addresses:
                    company_name = normalize_name(addr.company.name)
                    if company_name == name:
                        matched_company = {
                            "id": addr.company.id,
                            "name": addr.company.name,
                            "number": addr.company.number,
                            "maps_id": addr.company.maps_id,
                        }
                        break
                    ratio = fuzz.WRatio(company_name, name)
                    if ratio > FUZZY_MATCH_THRESHOLD and ratio > best_score:
                        best_score = ratio
                        matched_company = {
                            "id": addr.company.id,
                            "name": addr.company.name,
                            "number": addr.company.number,
                            "maps_id": addr.company.maps_id,
                        }

        # 4. Enrich result
        result = {
            "company_name": matched_company["name"] if matched_company else None,
            "vat_number": matched_company["number"] if matched_company else None,
            "company_id": matched_company["id"] if matched_company else None,
        }

        # 5. Save maps_id if missing
        if matched_company and matched_company.get("maps_id") != place_id and place_id:
            Company.objects.filter(id=matched_company["id"]).update(maps_id=place_id)
            matched_company["maps_id"] = place_id  # update local copy too

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