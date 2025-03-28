from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet, AnnualAccountViewSet, CompanySearchViewSet
from django.urls import path

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='companies')
router.register(r'companies/(?P<number>[^/.]+)/annual-accounts', AnnualAccountViewSet, basename='company-annual-accounts')

company_search = CompanySearchViewSet.as_view({'get': 'list'})

urlpatterns = [
    path('companies/search/', company_search, name='company-search'),  # must come BEFORE router.urls
] + router.urls