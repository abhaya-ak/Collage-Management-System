from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminNoticeViewSet

router = DefaultRouter()

# This automatically handles GET /notices/, POST /notices/, and GET /notices/{id}/
router.register(r'notices', AdminNoticeViewSet, basename='notice')

urlpatterns = [
    # Include the router
    path('', include(router.urls)),
]