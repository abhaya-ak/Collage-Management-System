"""Attendance routes -> mounted at /api/attendance/ by config.urls."""

from rest_framework.routers import DefaultRouter

from apps.attendance.views import AttendanceSessionViewSet

app_name = "attendance"

router = DefaultRouter()
router.register("sessions", AttendanceSessionViewSet, basename="attendance-session")

urlpatterns = router.urls
