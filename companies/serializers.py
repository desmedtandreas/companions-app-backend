from rest_framework import serializers
from .models import Company, Address, AnnualAccount, FinancialRubric, Administrator, Person

class FinancialRubricSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialRubric
        fields = ["code", "value"]


class AnnualAccountSerializer(serializers.ModelSerializer):
    financial_rubrics = FinancialRubricSerializer(many=True, read_only=True)

    class Meta:
        model = AnnualAccount
        fields = ["reference", "end_fiscal_year", "financial_rubrics"]


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["first_name", "last_name"]


class AdministratorSerializer(serializers.ModelSerializer):
    administering_company = serializers.StringRelatedField()
    representatives = PersonSerializer(many=True)

    class Meta:
        model = Administrator
        fields = ["administering_company", "mandate", "representatives"]
        
        
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["type", "street", "house_number", "postal_code", "city", "country"]
        

class CompanySerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    
    class Meta:
        model = Company
        fields = ["number", "name", "status", "type", "start_date", "addresses"]


class CompanyFullSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    annual_accounts = serializers.SerializerMethodField()

    class Meta(CompanySerializer.Meta):
        fields = CompanySerializer.Meta.fields + ["addresses", "annual_accounts"]

    def get_annual_accounts(self, obj):
        accounts = obj.annual_accounts.order_by("-end_fiscal_year")
        return AnnualAccountSerializer(accounts, many=True).data