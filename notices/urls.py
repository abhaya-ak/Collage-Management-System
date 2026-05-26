from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NoticeViewSet, AdminNoticeViewSet

router = DefaultRouter()
router.register(r'admin', AdminNoticeViewSet, basename='admin-notice')
router.register(r'',      NoticeViewSet,      basename='notice')
# NOTE: admin must be registered BEFORE '' to avoid route shadowing

urlpatterns = [
    path('', include(router.urls)),
]