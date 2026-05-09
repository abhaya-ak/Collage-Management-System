# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StudentProfileViewSet, 
    RoutineViewSet, 
    StudentResultViewSet, 
    LeaveRequestViewSet,
    TeacherRoutineViewSet,
    AttendanceViewSet,
    NoticeViewSet,
    TeacherFeedbackViewSet
)

router = DefaultRouter()

router.register(r'students', StudentProfileViewSet, basename='student')
router.register(r'routines', RoutineViewSet, basename='routine')
router.register(r'results', StudentResultViewSet, basename='result')
router.register(r'leaves', LeaveRequestViewSet, basename='leave')

router.register(r'teacher-routines', TeacherRoutineViewSet, basename='teacher-routine')
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'notices', NoticeViewSet, basename='notice')
router.register(r'feedback', TeacherFeedbackViewSet, basename='feedback')

urlpatterns = [
    path('', include(router.urls)),
]