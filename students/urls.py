from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StudentProfileViewSet, 
    RoutineViewSet, 
    StudentResultViewSet, 
    LeaveRequestViewSet
)

router = DefaultRouter()
router.register(r'students', StudentProfileViewSet, basename='student')
router.register(r'routines', RoutineViewSet, basename='routine')
router.register(r'results', StudentResultViewSet, basename='result')
router.register(r'leaves', LeaveRequestViewSet, basename='leave')

urlpatterns = [
    path('student/', include(router.urls)),
]