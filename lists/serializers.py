from rest_framework import serializers
from .models import List, ListItem, Label, Municipality
from companies.models import Company

class MunicipalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipality
        fields = ['id', 'name', 'code']

class CompanySerializer(serializers.ModelSerializer):
    address = serializers.SerializerMethodField()
    
    class Meta:
        model = Company
        fields = ['id', 'name', 'number', 'start_date', 'address', 'website', 'keyfigures']
        
    def get_address(self, obj):
        # Try to use prefetched addresses
        addresses = getattr(obj, '_prefetched_objects_cache', {}).get('addresses')
        if addresses is not None:
            print("Using prefetched addresses!")
            if addresses:
                address = addresses[0]
                return f"{address.street} {address.house_number}, {address.postal_code} {address.city}"
        else:
            print("Prefetch missing — falling back to query.")
            address = obj.addresses.all().first()
            if address:
                return f"{address.street} {address.house_number}, {address.postal_code} {address.city}"

        return None

class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ["id", "name"]

class ListItemSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    label = LabelSerializer(read_only=True)

    class Meta:
        model = ListItem
        fields = ['id', 'company', 'label', 'created_at']

class ListDetailSerializer(serializers.ModelSerializer):
    items = ListItemSerializer(many=True, read_only=True)
    labels = LabelSerializer(many=True, read_only=True)

    class Meta:
        model = List
        fields = ['id', 'name', 'slug', 'description', 'created_at', 'updated_at', 'items', 'labels', 'municipality_scores']
        read_only_fields = ['slug', 'created_at', 'updated_at']
        
class ListSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = List
        fields = ['id', 'name', 'slug', 'description', 'created_at', 'updated_at']
        read_only_fields = ['slug', 'created_at', 'updated_at']