from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from companies.models import Company
from .models import List, ListItem
from .serializers import ListDetailSerializer, ListSummarySerializer, ListItemSerializer
from .utils.export_excel import generate_companies_excel
from django.http import HttpResponse


class ListViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'

    def get_queryset(self):
        qs = List.objects.all().order_by('-created_at')
        if getattr(self, "action", None) in [
            "retrieve",
            "add_company",
            "add_companies",
            "remove_company",
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
