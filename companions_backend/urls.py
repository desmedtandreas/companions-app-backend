from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from maps_search.views import GoogleMapsPlacesViewSet

router = DefaultRouter()
router.register(r'maps', GoogleMapsPlacesViewSet, basename='maps')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),                # existing
    path('api/', include('companies.urls')), 
]
