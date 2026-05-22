# feedback/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeedbackViewSet, AdminFeedbackViewSet

router = DefaultRouter()
router.register(r'admin', AdminFeedbackViewSet, basename='admin-feedback')
# NOTE: admin registered before '' to avoid route shadowing

urlpatterns = [
    path('', include(router.urls)),
    path('', FeedbackViewSet.as_view({'post': 'create'})),  # POST /api/v1/feedback/
]