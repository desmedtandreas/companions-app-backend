import logging
import requests
from django.conf import settings
from companies.models import Company, Address
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)
FUZZY_MATCH_THRESHOLD = 85

FUZZY_MATCH_THRESHOLD = 85  # Adjust based on your needs


def enrich_with_company_data(places_data):
    enriched = []

    for place in places_data:
        formatted_address = place.get("address", "")
        matched_company = None
        best_score = 0

        if not formatted_address:
            enriched.append(place)
            continue

        # Use part of the input address to limit DB candidates (e.g. street or number)
        partial_query = formatted_address[:5]  # adjust depending on patterns in your data

        # Narrow DB query (PostgreSQL will use index here if you index 'street')
        possible_addresses = Address.objects.filter(
            street__icontains=partial_query
        ).select_related("company")

        for addr in possible_addresses:
            full_addr = addr.full_address()
            score = fuzz.WRatio(formatted_address[:-9], full_addr)

            if score > FUZZY_MATCH_THRESHOLD and score > best_score:
                matched_company = addr.company
                best_score = score

        if matched_company:
            place["vat_number"] = matched_company.enterprise_number
            place["company_id"] = matched_company.id
        else:
            place["vat_number"] = None
            place["company_id"] = None

        enriched.append(place)

    return enriched


def GoogleMapsPlacesAPI(textQuery):
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
        
    return filtered_data