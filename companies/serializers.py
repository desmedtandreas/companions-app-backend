from rest_framework import serializers
from .models import Company, Address, AnnualAccount, FinancialRubric, Administrator, Person, Participation

class FinancialRubricSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialRubric
        fields = ["code", "value"]
        
        
class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["first_name", "last_name"]
        
        
class AdministratorSerializer(serializers.ModelSerializer):
    administering_company = serializers.StringRelatedField()
    representatives = PersonSerializer(many=True)

    class Meta:
        model = Administrator
        fields = ["id", "administering_company", "representatives"]
        
        
class ParticipationSerializer(serializers.ModelSerializer):
    held_company = serializers.StringRelatedField()

    class Meta:
        model = Participation
        fields = ["id", "held_company", "percentage"]


class AnnualAccountSerializer(serializers.ModelSerializer):
    administrators = AdministratorSerializer(many=True, read_only=True)
    kpis = serializers.SerializerMethodField()
    participations = ParticipationSerializer(many=True, read_only=True)

    class Meta:
        model = AnnualAccount
        fields = ["reference", "end_fiscal_year", "administrators", "kpis", "participations"]
        
    def get_kpis(self, obj):
        return obj.calculate_kpis()
      
        
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["type", "street", "house_number", "postal_code", "city", "country"]
        

class CompanySerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    tags = serializers.ListField(child=serializers.CharField(), source='tags.names')
    
    class Meta:
        model = Company
        fields = ["number", "name", "status", "enterprise_type", "legalform", "legalform_short", "start_date", "website", "fin_fetch", "tags", "addresses"]