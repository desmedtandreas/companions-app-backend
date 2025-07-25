from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q
import threading
import openpyxl
import os
import re

from .models import Company
from .kbo_importer import import_kbo_open_data
from .serializers import CompanySerializer, AnnualAccountSerializer
from .financial_importer import import_financials

def parse_vat(value: str) -> str:
    value = value.upper().replace("BE", "")
    return re.sub(r"\D", "", value)

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
    
    @action(detail=False, methods=["post"])
    def bulk(self, request):
        numbers = request.data.get("numbers", [])
        if not isinstance(numbers, list):
            return Response({"error": "Expected a list of numbers."}, status=400)

        queryset = Company.objects.filter(number__in=numbers)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser])
    def upload_excel(self, request):
        file = request.FILES.get("file")
        column = request.data.get("column")

        if not file or not column:
            return Response({"error": "Both 'file' and 'column' are required."}, status=400)

        try:
            workbook = openpyxl.load_workbook(file)
            sheet = workbook.active
            header = [cell.value for cell in sheet[1]]

            if column not in header:
                return Response({"error": f"Column '{column}' not found."}, status=400)

            col_idx = header.index(column)
            vat_numbers = []

            for row in sheet.iter_rows(min_row=2, values_only=True):
                raw_value = row[col_idx]
                if raw_value:
                    vat = parse_vat(str(raw_value))
                    if vat:
                        vat_numbers.append(vat)

            queryset = Company.objects.filter(number__in=vat_numbers)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
        

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
    
class LoadKBODataView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        auth_header = request.headers.get('Authorization')
        if auth_header != f"{os.getenv('KBO_TRIGGER_TOKEN')}":
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        year = request.data.get("year")
        month = request.data.get("month")
        s3_prefix = request.data.get("s3_prefix")

        if not all([year, month, s3_prefix]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        threading.Thread(target=import_kbo_open_data, args=(s3_prefix,)).start()

        return Response({"status": "Loading started", "s3_prefix": s3_prefix}, status=status.HTTP_200_OK)