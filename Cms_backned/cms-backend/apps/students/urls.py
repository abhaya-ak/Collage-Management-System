"""Students routes -> mounted at /api/students/ by config.urls."""

from rest_framework.routers import DefaultRouter

from apps.students.views import StudentViewSet

app_name = "students"

router = DefaultRouter()
router.register("", StudentViewSet, basename="student")

urlpatterns = router.urls