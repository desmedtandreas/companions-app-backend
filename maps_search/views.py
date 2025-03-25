from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.decorators import action

import time

from django.core.cache import cache
from companies.models import Company

from maps_search.services import GoogleMapsPlacesAPI, enrich_with_company_data
from maps_search.serializers import GoogleMapsPlacesSerializer

class GoogleMapsPlacesViewSet(ViewSet):
    def list(self, request):
        return Response({"info": "This is the maps API root."})
    
    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        text_query = request.query_params.get('textQuery', '')
        if not text_query:
            return Response({"error": "textQuery parameter is required"}, status=400)
        
        cache_key = f"places_search:{text_query.lower()}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data, status=200)

        try:
            start = time.time()
            places = GoogleMapsPlacesAPI(text_query)
            print(f"API call took {time.time() - start} seconds")
            
            start = time.time()
            enriched_places = enrich_with_company_data(places)
            print(f"Enrichment took {time.time() - start} seconds")
            
            start = time.time()
            serializer = GoogleMapsPlacesSerializer(enriched_places, many=True)
            print(f"Serialization took {time.time() - start} seconds")
            
            cache.set(cache_key, serializer.data, timeout=3600)
            
            start = time.time()
            response = Response(serializer.data, status=200)
            print(f"Response building took {time.time() - start} seconds")
            
            return response
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
    @action(detail=False, methods=['post'], url_path='set-vat')
    def set_vat(self, request):
        vat_number = request.data.get('vat_number')
        place_id = request.data.get('place_id')
        text_query = request.data.get('text_query')

        if not vat_number or not place_id:
            return Response({"error": "vat_number and place_id are required"}, status=400)

        try:
            # Try to find company by VAT
            company = Company.objects.get(number=vat_number)
            if not company:
                return Response({"error": "Company not found with this VAT"}, status=404)
            
            company.maps_id = place_id
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
