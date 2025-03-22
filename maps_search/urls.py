from django.urls import path
from .views import GoogleMapsPlacesAPIView

urlpatterns = [
    path('', GoogleMapsPlacesAPIView.as_view(), name='google_maps_api'),
]