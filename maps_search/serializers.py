from rest_framework import serializers

class GoogleMapsPlacesSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    address = serializers.CharField(max_length=255)
    website = serializers.URLField()
    vat_number = serializers.CharField(max_length=255, allow_blank=True)
    company_id = serializers.IntegerField(allow_null=True)