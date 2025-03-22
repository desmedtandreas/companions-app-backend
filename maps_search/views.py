from rest_framework.views import APIView
from rest_framework.response import Response

from maps_search.services import GoogleMapsPlacesAPI, enrich_with_company_data
from maps_search.serializers import GoogleMapsPlacesSerializer

class GoogleMapsPlacesAPIView(APIView):
    def get(self, request):
        text_query = request.query_params.get('textQuery', '')
        if not text_query:
            return Response({"error": "textQuery parameter is required"}, status=400)
        
        try:
            places = GoogleMapsPlacesAPI(text_query)
            enriched_places = enrich_with_company_data(places)
            serializer = GoogleMapsPlacesSerializer(enriched_places, many=True)
            return Response(serializer.data, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
