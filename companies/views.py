from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q
import re

from .models import Company
from .serializers import CompanySerializer, AnnualAccountSerializer
from .financial_importer import import_financials

class CompanySearchViewSet(ReadOnlyModelViewSet):
    serializer_class = CompanySerializer

    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        # Normalize the query
        query = re.sub(r"\s+", " ", query).strip()
        
        qs = Company.objects.all()

        if query:
            qs = qs.filter(
                Q(name__icontains=query) | Q(number__icontains=query)
            )

        # Limit results and sort them by name
        return qs[:20]
        

class CompanyViewSet(ReadOnlyModelViewSet):
    serializer_class = CompanySerializer
    lookup_field = "number"

    def get_queryset(self):
        return Company.objects.all()

    def get_object(self):
        enterprise_number = self.kwargs.get("number")
        return get_object_or_404(Company, number=enterprise_number)

    @action(detail=True, methods=["get"], url_path="annual-accounts")
    def annual_accounts(self, request, number=None):        
        company = self.get_object()
        sync_requested = request.query_params.get("sync") == "true"
        has_financials = company.annual_accounts.exists()

        if sync_requested or not has_financials:
            # Optional: only delete if we actually had data
            if has_financials:
                company.annual_accounts.all().delete()

            import_financials(company.number)

        annual_accounts = company.annual_accounts.all().order_by("-end_fiscal_year")[:3]
        
        serializer = AnnualAccountSerializer(annual_accounts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=["post"], url_path="add-tag")
    def add_tag(self, request, number=None):
        company = self.get_object()
        tag = request.data.get("tag")
        
        if not tag:
            return Response({"error": "Tag name is required."}, status=400)
        
        company.tags.add(tag)
        return Response({"tags": list(company.tags.names())}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=["post"], url_path="remove-tag")
    def remove_tag(self, request, number=None):
        company = self.get_object()
        tag = request.data.get("tag")
        
        if not tag:
            return Response({"error": "Tag name is required."}, status=400)
        
        company.tags.remove(tag)
        return Response({"tags": list(company.tags.names())}, status=status.HTTP_200_OK)