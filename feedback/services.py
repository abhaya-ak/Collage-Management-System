# feedback/services.py
"""
Feedback domain service layer.

FeedbackService — message validation, teacher target validation,
                  resolve display labels
"""
from .models import Feedback


class FeedbackService:

    MIN_MESSAGE_LENGTH = 10
    MAX_MESSAGE_LENGTH = 2000

    @staticmethod
    def validate_message(message: str) -> str:
        message = message.strip()
        if len(message) < FeedbackService.MIN_MESSAGE_LENGTH:
            raise ValueError(
                f"Message is too short. "
                f"Please provide at least {FeedbackService.MIN_MESSAGE_LENGTH} characters."
            )
        if len(message) > FeedbackService.MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message cannot exceed {FeedbackService.MAX_MESSAGE_LENGTH} characters."
            )
        return message

    @staticmethod
    def validate_target_teacher(user) -> None:
        """
        Raises ValueError if the given user is not a registered Teacher.
        Prevents students from tagging admin accounts as 'teachers'.
        None is valid — means feedback is directed at the college.
        """
        if user is None:
            return
        from students.models import Teacher
        if not Teacher.objects.filter(user=user).exists():
            raise ValueError("The selected user is not a registered teacher.")

    @staticmethod
    def resolve_directed_at(feedback: Feedback) -> str:
        """
        Human-readable label for who the feedback is directed at.
        Used consistently across all serializers.
        """
        if feedback.target_teacher:
            u = feedback.target_teacher
            return f"{u.first_name} {u.last_name}".strip() or u.username
        return "College Administration"

    @staticmethod
    def resolve_teacher_name(user) -> str | None:
        """Resolves a User FK to a display name. Returns None if user is None."""
        if not user:
            return None
        return f"{user.first_name} {user.last_name}".strip() or user.username
