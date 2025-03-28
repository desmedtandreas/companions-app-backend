from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import connection
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

from .models import Company, AnnualAccount
from .serializers import CompanySerializer, CompanyFullSerializer, AnnualAccountSerializer
from .financial_importer import import_financials
from .utils import parse_enterprise_number_dotted

class CompanySearchViewSet(ReadOnlyModelViewSet):
    serializer_class = CompanySerializer

    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        qs = Company.objects.all()
        
        
        if 'postgresql' in connection.vendor:
            if query:
                
                search_vector = SearchVector('name', 'number')
                search_query = SearchQuery(query)
                search_rank = SearchRank(search_vector, search_query)
                
                qs = qs.annotate(
                    rank=search_rank
                ).filter(rank__gte=0.5).order_by('-rank')
                
        else:
            # Fallback for other databases
            if query:
                qs = qs.filter(
                    Q(name__icontains=query) | Q(number__icontains=query)
                )

        # Limit results and sort them by name
        return qs[:1000]
        

class CompanyViewSet(ReadOnlyModelViewSet):
    serializer_class = CompanySerializer
    lookup_field = "number"

    def get_queryset(self):
        return Company.objects.all()

    def get_object(self):
        enterprise_number = self.kwargs.get("number")
        parsed_number = parse_enterprise_number_dotted(enterprise_number)
        return get_object_or_404(Company, number=parsed_number)

    @action(detail=True, methods=["get"], url_path="full")
    def full(self, request, number=None):
        company = self.get_object()

        if not company.annual_accounts.exists():
            import_financials(company.number)

        serializer = CompanyFullSerializer(company)
        return Response(serializer.data)


class AnnualAccountViewSet(ReadOnlyModelViewSet):
    serializer_class = AnnualAccountSerializer

    def get_queryset(self):
        enterprise_number = self.kwargs.get("number")
        enterprise_number = parse_enterprise_number_dotted(enterprise_number)
        print(f"Fetching accounts for {enterprise_number}")
        # Try to fetch the company
        try:
            company = Company.objects.get(number=enterprise_number)
        except Company.DoesNotExist:
            print(f"Company {enterprise_number} not found")
            return AnnualAccount.objects.none()

        qs = AnnualAccount.objects.filter(company=company)

        # If none exist, trigger import and re-query
        if not qs.exists():
            print(f"Company {company} has no financial data, importing...")
            import_financials(enterprise_number)
            qs = AnnualAccount.objects.filter(company=company)

        return qs