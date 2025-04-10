from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from maps_search.views import GoogleMapsPlacesViewSet
from lists.views import ListViewSet

router = DefaultRouter()
router.register(r'lists', ListViewSet, basename='list')
router.register(r'maps', GoogleMapsPlacesViewSet, basename='maps')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/', include('companies.urls')),
]
