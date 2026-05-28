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
    # Explicit path avoids conflict with the router's API-root registered at ''.
    # Students POST to /api/v1/feedback/submit/ to submit feedback.
    path('submit/', FeedbackViewSet.as_view({'post': 'create'}), name='feedback-submit'),
]