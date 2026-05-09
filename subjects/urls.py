from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubjectViewSet

router = DefaultRouter()

# This single line creates all 5 requested endpoints!
router.register(r'subjects', SubjectViewSet, basename='subject')

urlpatterns = [
    path('', include(router.urls)),
]