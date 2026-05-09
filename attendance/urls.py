from django.urls import path
from .views import MarkAttendanceAPIView, StudentAttendanceReportAPIView

urlpatterns = [
    # POST endpoint for teachers
    path('attendance/mark/', MarkAttendanceAPIView.as_view(), name='mark-attendance'),
    path('attendance/student/<int:id>/', StudentAttendanceReportAPIView.as_view(), name='student-attendance-report'),
]