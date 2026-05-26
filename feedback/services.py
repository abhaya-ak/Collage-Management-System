# feedback/services.py
"""
Feedback domain service layer.

FeedbackService — message validation, teacher target validation,
                  display label resolution, status lifecycle + admin reply.
"""
from django.db import transaction
from django.utils import timezone

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
        None is valid — means feedback is directed at the college.
        """
        if user is None:
            return
        from students.models import Teacher
        if not Teacher.objects.filter(user=user).exists():
            raise ValueError("The selected user is not a registered teacher.")

    @staticmethod
    def validate_reply_content(admin_reply: str, status: str) -> str:
        """
        A reply message is required when marking feedback as RESOLVED or CLOSED.
        For PENDING / REVIEWED, the reply is optional.
        Returns the stripped reply string.
        """
        reply = admin_reply.strip() if admin_reply else ''
        if status in (Feedback.Status.RESOLVED, Feedback.Status.CLOSED) and not reply:
            raise ValueError(
                "A reply message is required when marking feedback as "
                f"'{Feedback.Status(status).label}'. "
                "The student needs to know the outcome."
            )
        return reply

    @staticmethod
    @transaction.atomic
    def reply(feedback: Feedback, status: str, admin_reply: str, replied_by) -> Feedback:
        """
        Admin responds to a feedback item.

        - Always updates status.
        - Updates admin_reply, replied_at, replied_by when reply text is provided.
        - Uses filter().update() to avoid race conditions.
        - Returns refreshed Feedback instance.

        Raises ValueError if reply content rules are violated.
        """
        admin_reply = FeedbackService.validate_reply_content(admin_reply, status)

        update_fields = {'status': status}
        if admin_reply:
            update_fields['admin_reply'] = admin_reply
            update_fields['replied_at']  = timezone.now()
            update_fields['replied_by']  = replied_by

        Feedback.objects.filter(pk=feedback.pk).update(**update_fields)
        feedback.refresh_from_db()
        return feedback

    # ── Display label helpers ──────────────────────────────────────────────────

    @staticmethod
    def resolve_directed_at(feedback: Feedback) -> str:
        if feedback.target_teacher:
            u = feedback.target_teacher
            return f"{u.first_name} {u.last_name}".strip() or u.username
        return "College Administration"

    @staticmethod
    def resolve_teacher_name(user) -> str | None:
        if not user:
            return None
        return f"{user.first_name} {user.last_name}".strip() or user.username
