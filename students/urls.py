# students/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    StudentProfileViewSet,
    TeacherViewSet,
    LeaveRequestViewSet,
    StudentResultViewSet,
    TeacherRoutineViewSet,
    TeacherFeedbackViewSet,
)

router = DefaultRouter()
router.register(r'profiles',         StudentProfileViewSet,  basename='student-profile')
router.register(r'teachers',         TeacherViewSet,         basename='teacher')
router.register(r'leaves',           LeaveRequestViewSet,    basename='leave-request')
router.register(r'results',          StudentResultViewSet,   basename='student-result')
router.register(r'teacher-routines', TeacherRoutineViewSet,  basename='teacher-routine')
router.register(r'teacher-feedback', TeacherFeedbackViewSet, basename='teacher-feedback')

urlpatterns = [
    path('', include(router.urls)),
]