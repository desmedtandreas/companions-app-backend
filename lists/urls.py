from rest_framework.routers import DefaultRouter
from .views import ListViewSet

router = DefaultRouter()
router.register(r'', ListViewSet, basename='list')

urlpatterns = router.urls