from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeedbackViewSet

router = DefaultRouter()

# This handles both the GET (for admins) and POST (for students) securely
router.register(r'feedback', FeedbackViewSet, basename='feedback')

urlpatterns = [
    path('', include(router.urls)),
]