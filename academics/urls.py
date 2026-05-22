from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FacultyViewSet,
    RoutineViewSet,
    ExamRoutineViewSet,
    ResultViewSet,
)


router = DefaultRouter()
router.register(r'faculties',      FacultyViewSet,     basename='faculty')
router.register(r'routines',       RoutineViewSet,     basename='routine')
router.register(r'exam-routines',  ExamRoutineViewSet, basename='exam-routine')
router.register(r'results',        ResultViewSet,      basename='result')

urlpatterns = [
    path('', include(router.urls)),
]