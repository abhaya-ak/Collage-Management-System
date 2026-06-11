"""Faculty routes -> mounted at /api/faculty/ by config.urls."""

from rest_framework.routers import DefaultRouter

from apps.faculty.views import FacultyViewSet

app_name = "faculty"

router = DefaultRouter()
router.register("", FacultyViewSet, basename="faculty")

urlpatterns = router.urls
