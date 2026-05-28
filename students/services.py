# students/services.py
"""
Students domain service layer.

StudentService      — profile uniqueness, year validation
LeaveRequestService — date range validation, status logic,
                      approve / reject transitions
"""
from django.db import transaction
from django.utils import timezone

from .models import Student, LeaveRequest


class StudentService:

    @staticmethod
    def validate_unique_profile(user, exclude_pk=None) -> None:
        """Raises ValueError if a Student profile already exists for this user."""
        qs = Student.objects.filter(user=user)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValueError("A student profile already exists for this user.")

    @staticmethod
    def validate_year(value: int) -> None:
        if value < 1:
            raise ValueError("Year must be at least 1.")

    @staticmethod
    def get_student_for_user(user) -> Student:
        """
        Returns the Student instance for the given user.
        Raises ValueError if no student profile exists.
        Used by views to get the student from the auth token.
        """
        try:
            return Student.objects.select_related('user').get(user=user)
        except Student.DoesNotExist:
            raise ValueError("No student profile found for this user.")


class LeaveRequestService:

    @staticmethod
    def validate_from_date_not_past(from_date) -> None:
        if from_date < timezone.now().date():
            raise ValueError("Leave cannot be requested for a past date.")

    @staticmethod
    def validate_date_range(from_date, to_date) -> None:
        if from_date and to_date and to_date < from_date:
            raise ValueError("End date cannot be before start date.")

    @staticmethod
    def get_status_label(leave_request: LeaveRequest) -> str:
        return "Approved" if leave_request.approved else "Pending"

    @staticmethod
    @transaction.atomic
    def submit(student: Student, from_date, to_date, reason: str) -> LeaveRequest:
        """Creates a new leave request for a student."""
        LeaveRequestService.validate_from_date_not_past(from_date)
        LeaveRequestService.validate_date_range(from_date, to_date)
        return LeaveRequest.objects.create(
            student   = student,
            from_date = from_date,
            to_date   = to_date,
            reason    = reason,
            approved  = False,
        )

    @staticmethod
    @transaction.atomic
    def approve(leave_request: LeaveRequest) -> LeaveRequest:
        """
        Marks a leave request as approved.
        Raises ValueError if already approved (idempotency guard).
        """
        if leave_request.approved:
            raise ValueError("This leave request is already approved.")
        leave_request.approved = True
        leave_request.save(update_fields=['approved'])
        return leave_request

    @staticmethod
    @transaction.atomic
    def reject(leave_request: LeaveRequest) -> LeaveRequest:
        """
        Marks a leave request as rejected / reverted to pending.
        Raises ValueError if already in pending state.
        """
        if not leave_request.approved:
            raise ValueError("This leave request is already pending / not approved.")
        leave_request.approved = False
        leave_request.save(update_fields=['approved'])
        return leave_request
