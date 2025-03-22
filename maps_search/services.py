import logging
import requests
from django.conf import settings
from django.core.cache import cache
from companies.models import Address
from rapidfuzz import process, fuzz
import hashlib
import copy

logger = logging.getLogger(__name__)
FUZZY_MATCH_THRESHOLD = 85
CACHE_TIMEOUT = 3600  # seconds (1 hour)


def enrich_with_company_data(places_data):
    enriched = []
    address_lookup = {}

    # Step 1: Collect partial queries
    partials = set()
    for place in places_data:
        addr = place.get("address", "")
        if addr:
            partials.add(addr[:5].lower())

    # Step 2: Query all matching addresses once
    from django.db.models import Q
    query = Q()
    for p in partials:
        query |= Q(street__icontains=p)

    addresses = Address.objects.filter(query).select_related("company")

    # Step 3: Build full_address to Address object map
    for addr in addresses:
        full_addr = addr.full_address()
        address_lookup[full_addr] = addr

    address_corpus = list(address_lookup.keys())  # list of strings

    # Step 4: Enrich each place
    for place in places_data:
        formatted_address = place.get("address", "")
        if not formatted_address:
            place.update({"vat_number": None, "company_id": None})
            enriched.append(place)
            continue

        cache_key = f"enriched_place:{hashlib.md5(formatted_address.encode()).hexdigest()}"
        cached_result = cache.get(cache_key)

        if cached_result:
            place.update(copy.deepcopy(cached_result))
            enriched.append(place)
            continue

        # Step 5: Fuzzy match from preloaded corpus
        match = process.extractOne(
            formatted_address,
            address_corpus,
            scorer=fuzz.WRatio,
            score_cutoff=FUZZY_MATCH_THRESHOLD
        )

        if match:
            matched_addr = address_lookup[match[0]]
            result = {
                "vat_number": matched_addr.company.enterprise_number,
                "company_id": matched_addr.company.id
            }
        else:
            result = {
                "vat_number": None,
                "company_id": None
            }

        cache.set(cache_key, copy.deepcopy(result), CACHE_TIMEOUT)
        place.update(result)
        enriched.append(place)

    return enriched

def GoogleMapsPlacesAPI(textQuery):
    cache_key = f"google_places:{hashlib.md5(textQuery.encode()).hexdigest()}"
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

    return filtered_data