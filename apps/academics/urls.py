"""Academics routes -> mounted at /api/academics/ by config.urls."""

from rest_framework.routers import DefaultRouter

from apps.academics.views import (
    AcademicLeaveViewSet,
    AcademicYearViewSet,
    ProgramSemesterSubjectViewSet,
    ProgramViewSet,
    RoutineViewSet,
    SectionViewSet,
    SemesterViewSet,
    SubjectViewSet,
)

app_name = "academics"

router = DefaultRouter()
router.register("academic-years", AcademicYearViewSet, basename="academic-year")
router.register("programs", ProgramViewSet, basename="program")
router.register("semesters", SemesterViewSet, basename="semester")
router.register("subjects", SubjectViewSet, basename="subject")
router.register("sections", SectionViewSet, basename="section")
router.register("curriculum", ProgramSemesterSubjectViewSet, basename="curriculum")
router.register("routines", RoutineViewSet, basename="routine")
router.register("academic-leaves", AcademicLeaveViewSet, basename="academic-leave")

urlpatterns = router.urls
