import logging
import requests
from django.conf import settings
from django.core.cache import cache
from companies.models import Company, Address
from rapidfuzz import fuzz
import hashlib
import json

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 85  # Adjust based on your needs
CACHE_TIMEOUT = 3600


def enrich_with_company_data(places_data):
    enriched = []

    for place in places_data:
        formatted_address = place.get("address", "")
        matched_company = None
        best_score = 0

        if not formatted_address:
            enriched.append(place)
            continue

        cache_key = f"enriched_place:{hashlib.md5(formatted_address.encode()).hexdigest()}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            place.update(cached_result)
            enriched.append(place)
            continue
        
        result = {
            "vat_number": matched_company.enterprise_number if matched_company else None,
            "company_id": matched_company.id if matched_company else None
        }
        
        cache.set(cache_key, result, CACHE_TIMEOUT)
        
        place.update(result)
        enriched.append(place)
        
        return enriched
    
def perform_fuzzy_matching(formatted_address):
    partial_query = formatted_address[:5].lower()

    possible_addresses = Address.objects.filter(
        street__icontains=partial_query
    ).select_related("company")
    
    best_score = 0
    matched_company = None

    for addr in possible_addresses:
        full_addr = addr.full_address()
        score = fuzz.WRatio(formatted_address[:-9], full_addr)

        if score > FUZZY_MATCH_THRESHOLD and score > best_score:
            matched_company = addr.company
            best_score = score

    return matched_company



def GoogleMapsPlacesAPI(textQuery):
    cache_key = f"google_places:{hashlib.md5(textQuery.encode()).hexdigest()}"
    cached_response = cache.get(cache_key)
    
    if cached_response is not None:
        return cached_response
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.websiteUri"
    }
    
    payload = {
        "textQuery" : textQuery,
        "locationRestriction": {
            "rectangle": {
            "low": {
                "latitude": 51,
                "longitude": 2.5
            },
            "high": {
                "latitude": 51.5,
                "longitude": 6
            }
            }
        }
    }
    
    try:
        response = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers=headers,
            json=payload,
        )
        data = response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {e}")

    filtered_data = []
    for place in data.get("places", []):
        filtered_data.append({
            'name': place.get('displayName').get('text'),
            'address': place.get('formattedAddress'),
            'website': place.get('websiteUri'),
            'vat_number': None,
            'company_id': None,
        })
        
    cache.set(cache_key, filtered_data, CACHE_TIMEOUT)
        
    return filtered_data