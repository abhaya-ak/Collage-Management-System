# subjects/services.py
"""
Subjects domain service layer.

SubjectService — code uniqueness, marks validation
"""
from .models import Subject


class SubjectService:

    @staticmethod
    def validate_code_unique(code: str, exclude_pk=None) -> str:
        """
        Normalizes code to uppercase and raises ValueError if already taken.
        Returns the normalized code.
        """
        code = code.strip().upper()
        qs = Subject.objects.filter(code__iexact=code)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValueError(f"A subject with code '{code}' already exists.")
        return code

    @staticmethod
    def validate_pass_marks(pass_marks: int) -> None:
        if pass_marks < 1:
            raise ValueError("Pass marks must be at least 1.")

    @staticmethod
    def validate_marks_range(full_marks, pass_marks) -> None:
        """Raises ValueError if pass_marks >= full_marks."""
        if full_marks is not None and pass_marks is not None:
            if pass_marks >= full_marks:
                raise ValueError(
                    f"Pass marks ({pass_marks}) must be "
                    f"strictly less than full marks ({full_marks})."
                )
