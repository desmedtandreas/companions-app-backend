from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from companies.models import Company
from .models import List, ListItem
from .serializers import ListSerializer, ListItemSerializer
from .utils.export_excel import generate_companies_excel
from django.http import HttpResponse


class ListViewSet(viewsets.ModelViewSet):
    queryset = List.objects.all().order_by('-created_at')
    serializer_class = ListSerializer
    lookup_field = 'slug'
    
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

        removed_count = 0
        errors = []

        for number in company_numbers:
            try:
                company = Company.objects.get(number=number)
                list_item = ListItem.objects.get(list=list_instance, company=company)
                list_item.delete()
                removed_count += 1
            except Company.DoesNotExist:
                errors.append(f'Company {number} not found.')
            except ListItem.DoesNotExist:
                errors.append(f'Company {number} not in list.')
            except Exception as e:
                errors.append(f'Error with {number}: {str(e)}')

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

        for company in companies:
            list_item, created = ListItem.objects.get_or_create(
                list=list_instance,
                company=company
            )
            if created:
                created_items.append(company.number)
        
        if created_items:
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
