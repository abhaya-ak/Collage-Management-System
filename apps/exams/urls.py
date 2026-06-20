"""Exam routes -> mounted at /api/exams/ by config.urls."""

from rest_framework.routers import DefaultRouter

from apps.exams.views import (
    ExamScheduleViewSet,
    ExamViewSet,
    MarkViewSet,
    ResultViewSet,
)

app_name = "exams"

router = DefaultRouter()
router.register("exams", ExamViewSet, basename="exam")
router.register("schedules", ExamScheduleViewSet, basename="exam-schedule")
router.register("marks", MarkViewSet, basename="mark")
router.register("results", ResultViewSet, basename="result")

urlpatterns = router.urls
