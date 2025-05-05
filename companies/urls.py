from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet, CompanySearchViewSet, LoadKBODataView
from django.urls import path

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='companies')
router.register(r'company-search', CompanySearchViewSet, basename='company-search')

urlpatterns = [
    path('companies/load-kbo-data/', LoadKBODataView.as_view(), name='load-kbo-data'),
] + router.urls