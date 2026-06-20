"""Faculty routes -> mounted at /api/faculty/ by config.urls."""

from rest_framework.routers import DefaultRouter

from apps.faculty.views import FacultyLeaveViewSet, FacultyViewSet

app_name = "faculty"

router = DefaultRouter()
# Register "leaves" BEFORE the "" faculty viewset so /api/faculty/leaves/ is not
# captured as a faculty detail (pk="leaves").
router.register("leaves", FacultyLeaveViewSet, basename="faculty-leave")
router.register("", FacultyViewSet, basename="faculty")

urlpatterns = router.urls
