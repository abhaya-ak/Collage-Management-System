# feedback/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import FeedbackViewSet, StudentFeedbackViewSet, AdminFeedbackViewSet

router = DefaultRouter()
# admin registered before 'my' to prevent any shadowing
router.register(r'admin', AdminFeedbackViewSet, basename='admin-feedback')
router.register(r'my',    StudentFeedbackViewSet, basename='my-feedback')

urlpatterns = [
    path('', include(router.urls)),
    path('', FeedbackViewSet.as_view({'post': 'create'})),  # POST /api/v1/feedback/
]