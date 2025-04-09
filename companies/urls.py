from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet, CompanySearchViewSet
from django.urls import path

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='companies')

company_search = CompanySearchViewSet.as_view({'get': 'list'})

urlpatterns = [
    path('companies/search/', company_search, name='company-search'),  # must come BEFORE router.urls
] + router.urls