"""Selectors — optimized read queries for the exam/result domain."""

from django.db.models import Prefetch

from apps.exams.models import Exam, ExamSchedule, Mark, Result, ResultItem


def exam_list():
    return Exam.objects.select_related("academic_year", "program", "semester")


def exam_detail_qs():
    return exam_list().prefetch_related(
        Prefetch(
            "schedules",
            queryset=ExamSchedule.objects.select_related("subject", "section"),
        )
    )


def exam_schedule_list():
    return ExamSchedule.objects.select_related("exam", "subject", "section")


def mark_list():
    return Mark.objects.select_related(
        "exam_schedule__exam", "exam_schedule__subject", "student", "entered_by"
    )


def student_marks(student):
    return mark_list().filter(student=student)


def result_list():
    return Result.objects.select_related("student", "exam")


def student_results(student):
    return result_list().filter(student=student)


def result_detail_qs():
    return result_list().prefetch_related(
        Prefetch("items", queryset=ResultItem.objects.select_related("subject"))
    )
