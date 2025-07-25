from rest_framework import viewsets
from rest_framework.generics import ListAPIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from companies.models import Company
from .models import List, ListItem, Label, Municipality
from .serializers import ListDetailSerializer, ListSummarySerializer, ListItemSerializer, LabelSerializer, MunicipalitySerializer
from .utils.export_excel import generate_companies_excel
from django.http import HttpResponse
from companies.tasks import trigger_financial_import_task
import pandas as pd
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework.parsers import MultiPartParser

class ListViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'

    def get_queryset(self):
        qs = List.objects.all().order_by('-created_at')
        if getattr(self, "action", None) in [
            "retrieve",
            "export_excel",
        ]:
            qs = qs.prefetch_related(
                "items__company__addresses",
                "items__company__annual_accounts__financial_rubrics",
            )
        return qs
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ListSummarySerializer  # define this separately
        return ListDetailSerializer
    
    @action(detail=True, methods=['post'], url_path='add-company')
    def add_company(self, request, slug=None):
        list_instance = self.get_object()
        company_number = request.data.get('company')

        if not company_number:
            return Response({'error': 'Missing "company" ID in request body.'}, status=400)

        try:
            company = Company.objects.get(pk=company_number)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found.'}, status=404)

        list_item, created = ListItem.objects.get_or_create(list=list_instance, company=company)
        if not created:
            return Response({'message': 'Company already in list.'}, status=200)
        
        if created:
            list_instance.save()

        return Response(
            ListItemSerializer(list_item).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], url_path='remove-companies')
    def remove_company(self, request, slug=None):
        list_instance = self.get_object()
        company_numbers = request.data.get('companies')

        if not company_numbers or not isinstance(company_numbers, list):
            return Response({'error': 'Missing or invalid "companies" list in request body.'}, status=status.HTTP_400_BAD_REQUEST)

        errors = []

        companies = Company.objects.filter(number__in=company_numbers)
        existing_numbers = set(companies.values_list('number', flat=True))
        missing_numbers = set(company_numbers) - existing_numbers
        errors.extend([f'Company {n} not found.' for n in missing_numbers])

        items = ListItem.objects.filter(list=list_instance, company__in=companies)
        existing_items_numbers = set(items.values_list('company__number', flat=True))
        not_in_list = existing_numbers - existing_items_numbers
        errors.extend([f'Company {n} not in list.' for n in not_in_list])

        removed_count = items.count()
        if removed_count:
            items.delete()
            list_instance.save()

        return Response({
            'removed': removed_count,
            'errors': errors,
        }, status=status.HTTP_200_OK)
        
    @action(detail=True, methods=['post'], url_path='add-companies')
    def add_companies(self, request, slug=None):
        list_instance = self.get_object()
        company_numbers = request.data.get('companies', [])

        if not isinstance(company_numbers, list) or not company_numbers:
            return Response({'error': 'companies must be a non-empty list of numbers'}, status=400)

        from companies.models import Company

        created_items = []

        companies = Company.objects.filter(number__in=company_numbers)
        existing_company_ids = set(
            ListItem.objects.filter(list=list_instance, company__in=companies)
            .values_list('company_id', flat=True)
        )

        new_items = []
        for company in companies:
            if company.id not in existing_company_ids:
                new_items.append(ListItem(list=list_instance, company=company))
                created_items.append(company.number)

        if new_items:
            ListItem.objects.bulk_create(new_items)
            list_instance.save()

            for item in new_items:
                print(f"Added {item.company_id} to list {list_instance.name}")
                trigger_financial_import_task.delay(item.company_id)

        return Response(
            {'added': len(created_items), 'added_companies': created_items},
            status=status.HTTP_201_CREATED
        )
        
    @action(detail=True, methods=['post'], url_path='export-excel')
    def export_excel(self, request, slug=None):
        list_instance = self.get_object()

        company_numbers = request.data.get('companies', None)

        if not company_numbers or not isinstance(company_numbers, list) or len(company_numbers) == 0:
            company_numbers = list_instance.items.values_list('company__number', flat=True)
            if company_numbers is None:
                return Response({'error': 'No companies found in the list.'}, status=status.HTTP_400_BAD_REQUEST)

        companies = Company.objects.filter(number__in=company_numbers)
        
        excel_file = generate_companies_excel(companies, list_instance.name)
        
        response = HttpResponse(
            excel_file,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
        filename = f"lijst_{list_instance.slug}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response
    
    @action(detail=True, methods=['get'], url_path='labels')
    def get_labels(self, request, slug=None):
        list_instance = self.get_object()
        labels = list_instance.labels.all()
        serializer = LabelSerializer(labels, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='create-label')
    def create_label(self, request, slug=None):
        list_instance = self.get_object()
        label_name = request.data.get('name')

        if not label_name:
            return Response({'error': 'Missing "name" in request body.'}, status=400)

        label, created = Label.objects.get_or_create(list=list_instance, name=label_name)
        if not created:
            return Response({'message': 'Label already exists.'}, status=200)

        return Response(LabelSerializer(label).data, status=status.HTTP_201_CREATED)
        
    @action(detail=True, methods=['post'], url_path='assign-label')
    def assign_label(self, request, slug=None):
        list_instance = self.get_object()
        label_id = request.data.get('label')
        company_number = request.data.get('company')

        if not label_id or not company_number:
            return Response({'error': 'Missing label or company number'}, status=400)

        try:
            label = Label.objects.get(id=label_id)
        except Label.DoesNotExist:
            return Response({'error': 'Label not found'}, status=404)

        try:
            company = Company.objects.get(number=company_number)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)

        try:
            item = ListItem.objects.get(list=list_instance, company=company)
        except ListItem.DoesNotExist:
            return Response({'error': 'Company not in list'}, status=400)

        item.label = label
        item.save()

        return Response({'message': 'Label assigned successfully'})
    
    @action(detail=True, methods=['post'], url_path='update-municipality-scores')
    def update_municipality_scores(self, request, slug=None):
        list_instance = self.get_object()
        scores = request.data.get('municipality_scores')

        if not isinstance(scores, dict):
            return Response({'error': 'municipality_scores must be a JSON object'}, status=400)

        # ✅ New validation: every value must be a number (float or int)
        invalid_entries = {
            k: v for k, v in scores.items()
            if not isinstance(v, (int, float))
        }

        if invalid_entries:
            return Response({'error': 'All values must be numbers', 'invalid': invalid_entries}, status=400)

        list_instance.municipality_scores = scores
        list_instance.save()

        return Response({'status': 'success', 'municipality_scores': list_instance.municipality_scores})
    
    @action(detail=True, methods=['post'], url_path='upload-municipality-scores')
    def upload_municipality_scores(self, request, slug=None):
        list_instance = self.get_object()
        excel_file = request.FILES.get("file")

        if not excel_file or not isinstance(excel_file, InMemoryUploadedFile):
            return Response({"error": "No valid Excel file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_excel(excel_file)
        except Exception as e:
            return Response({"error": f"Failed to parse Excel file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        if "Gemeente" not in df.columns or "Score" not in df.columns:
            return Response({"error": "Excel must contain 'Gemeente' and 'Score' columns."}, status=status.HTTP_400_BAD_REQUEST)

        df["Gemeente"] = df["Gemeente"].str.strip().str.lower()

        muni_lookup = {
            m.name.strip().lower(): m.code
            for m in Municipality.objects.all()
        }

        scores = {}
        skipped = []

        for _, row in df.iterrows():
            name = row["Gemeente"]
            score = row["Score"]

            code = muni_lookup.get(name)
            if code and isinstance(score, (float, int)):
                scores[code] = float(score)
            else:
                skipped.append(name)

        list_instance.municipality_scores = scores
        list_instance.save()

        return Response({
            "status": "success",
            "imported_count": len(scores),
            "municipality_scores": scores 
        })
    
    @action(detail=True, methods=['post'], url_path='import-companies', parser_classes=[MultiPartParser])
    def import_companies_from_excel(self, request, slug=None):
        list_instance = self.get_object()
        excel_file = request.FILES.get("file")

        if not excel_file or not isinstance(excel_file, InMemoryUploadedFile):
            return Response({"error": "No valid Excel file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_excel(excel_file, dtype={"Ondernemingsnummer": str})
        except Exception as e:
            return Response({"error": f"Failed to read Excel file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        if "Ondernemingsnummer" not in df.columns:
            return Response({"error": "Excel must contain a column 'Ondernemingsnummer'."}, status=status.HTTP_400_BAD_REQUEST)

        numbers = df["Ondernemingsnummer"].dropna().astype(str)
        numbers = numbers[numbers.str.len() > 0].unique().tolist()
        print(numbers)

        if not numbers:
            return Response({"error": "No valid enterprise numbers found in Excel."}, status=status.HTTP_400_BAD_REQUEST)

        companies = Company.objects.filter(number__in=numbers)
        existing_company_ids = set(
            ListItem.objects.filter(list=list_instance, company__in=companies)
            .values_list('company_id', flat=True)
        )

        created_items = []
        new_items = []

        for company in companies:
            if company.id not in existing_company_ids:
                new_items.append(ListItem(list=list_instance, company=company))
                created_items.append(company.number)

        if new_items:
            ListItem.objects.bulk_create(new_items)
            list_instance.save()

            # Trigger async financial import
            for item in new_items:
                trigger_financial_import_task.delay(item.company_id)

        return Response({
            "status": "success",
            "added": len(created_items),
            "added_companies": created_items,
            "not_found": list(set(numbers) - set(companies.values_list("number", flat=True))),
        })


class MunicipalityListView(ListAPIView):

    queryset = Municipality.objects.all().order_by('name')
    serializer_class = MunicipalitySerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)  # Use the default list behavior

