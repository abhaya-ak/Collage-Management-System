# attendance/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StudentAttendanceViewSet,
    TeacherAttendanceViewSet,
    AdminAttendanceViewSet,
)

router = DefaultRouter()
router.register(r'my',    StudentAttendanceViewSet, basename='my-attendance')
router.register(r'mark',  TeacherAttendanceViewSet, basename='mark-attendance')
router.register(r'admin', AdminAttendanceViewSet,   basename='admin-attendance')

urlpatterns = [
    path('', include(router.urls)),
]