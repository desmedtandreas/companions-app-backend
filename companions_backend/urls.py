from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from maps_search.views import GoogleMapsPlacesViewSet
from lists.views import ListViewSet
from debug_toolbar.toolbar import debug_toolbar_urls

router = DefaultRouter()
router.register(r'lists', ListViewSet, basename='list')
router.register(r'maps', GoogleMapsPlacesViewSet, basename='maps')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/', include('companies.urls')),
] + debug_toolbar_urls()
