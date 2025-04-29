from rest_framework import serializers
from .models import List, ListItem
from companies.models import Company

class CompanySerializer(serializers.ModelSerializer):
    address = serializers.SerializerMethodField()
    
    class Meta:
        model = Company
        fields = ['id', 'name', 'number', 'start_date', 'address', 'website', 'keyfigures']
        
    def get_address(self, obj):
        address = obj.addresses.all().first()
        if address:
            return f"{address.street} {address.house_number}, {address.postal_code} {address.city}"
        return None

class ListItemSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = ListItem
        fields = ['id', 'company', 'created_at']

class ListSerializer(serializers.ModelSerializer):
    items = ListItemSerializer(many=True, read_only=True)

    class Meta:
        model = List
        fields = ['id', 'name', 'slug', 'description', 'created_at', 'updated_at', 'items']
        read_only_fields = ['slug', 'created_at', 'updated_at']