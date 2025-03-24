from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.decorators import action

from django.core.cache import cache

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
            places = GoogleMapsPlacesAPI(text_query)
            enriched_places = enrich_with_company_data(places)
            serializer = GoogleMapsPlacesSerializer(enriched_places, many=True)
            cache.set(cache_key, serializer.data, timeout=3600)
            return Response(serializer.data, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
