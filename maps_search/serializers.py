from rest_framework import serializers
 
class PlaceSerializer(serializers.Serializer):
    place_id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    company_name = serializers.CharField(max_length=255)
    formatted_address = serializers.CharField(max_length=255)
    website = serializers.URLField()
    vat_number = serializers.CharField(max_length=255, allow_blank=True)
    company_id = serializers.IntegerField(allow_null=True)
    
class GoogleMapsPlacesSerializer(serializers.Serializer):
    places = PlaceSerializer(many=True)
    nextPageToken = serializers.CharField(max_length=1000, allow_blank=True, required=False)
    