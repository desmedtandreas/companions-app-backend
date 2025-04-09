from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.decorators import action

import time
import hashlib

from django.core.cache import cache
from companies.models import Company

from maps_search.services import GoogleMapsGeocodeAPI, GoogleMapsPlacesAPI, enrich_with_company_data
from maps_search.serializers import GoogleMapsPlacesSerializer

class GoogleMapsPlacesViewSet(ViewSet):
    def list(self, request):
        return Response({"info": "This is the maps API root."})
    
    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        text_query = request.query_params.get('textQuery', '')
        address = request.query_params.get('location', '')
        radius = request.query_params.get('radius', 50)
        next_page_token = request.query_params.get('nextPageToken', None)
        print("next_page_token: ", next_page_token)
        if not text_query:
            return Response({"error": "textQuery parameter is required"}, status=400)

        try:
            start = time.time()
            if address:
                geometry = GoogleMapsGeocodeAPI(address)
                latitude = geometry['latitude']
                longitude = geometry['longitude']
            else:
                latitude = '51.2211097'
                longitude = '4.3997082'
                
            print(latitude, longitude)
            data = GoogleMapsPlacesAPI(text_query, latitude, longitude, radius, next_page_token)
            print("Processing places took", time.time() - start, "seconds")
            
            start = time.time()
            data['places'] = enrich_with_company_data(data['places'])
            print("Enriching places took", time.time() - start, "seconds")
            
            start = time.time()
            serializer = GoogleMapsPlacesSerializer(instance=data)
            print("Serializing places took", time.time() - start, "seconds")
            
            return Response(serializer.data, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
    @action(detail=False, methods=['post'], url_path='set-vat')
    def set_vat(self, request):
        vat_number = request.data.get('vat_number')
        place_id = request.data.get('place_id')
        text_query = request.data.get('text_query')
        website = request.data.get('website')

        if not vat_number or not place_id:
            return Response({"error": "vat_number and place_id are required"}, status=400)

        try:
            # Try to find company by VAT
            company = Company.objects.get(number=vat_number)
            if not company:
                return Response({"error": "Company not found with this VAT"}, status=404)
            
            company.maps_id = place_id
            company.website = website
            company.save()
            
            cache_key = f"places_search:{text_query.lower()}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                for place in cached_data:
                    if place.get("place_id") == place_id:
                        place.update({
                            "company_id": company.id,
                            "vat_number": company.number,
                            "company_name": company.name,
                        })
                cache.set(cache_key, cached_data, timeout=3600)
                
            enriched_place = {
                "company_name": company.name,
                "vat_number": company.number,
                "company_id": company.id,
            }

            return Response(enriched_place, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
