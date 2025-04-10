from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from companies.models import Company
from .models import List, ListItem
from .serializers import ListSerializer, ListItemSerializer


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
    
    @action(detail=True, methods=['post'], url_path='remove-company')
    def remove_company(self, request, slug=None):
        list_instance = self.get_object()
        company_number = request.data.get('company')

        if not company_number:
            return Response({'error': 'Missing "company" ID in request body.'}, status=400)

        try:
            company = Company.objects.get(number=company_number)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found.'}, status=404)

        try:
            list_item = ListItem.objects.get(list=list_instance, company=company)
            list_item.delete()
            list_instance.save()
            return Response({'message': 'Company removed from list.'}, status=200)
        except ListItem.DoesNotExist:
            return Response({'error': 'Company not in list.'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
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
