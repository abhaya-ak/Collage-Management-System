# notices/services.py
"""
Notices domain service layer.

NoticeService — content validation, emergency audience rule, read tracking.
"""
from .models import Notice, NoticeRead


class NoticeService:

    @staticmethod
    def validate_title(title: str) -> str:
        title = title.strip()
        if not title:
            raise ValueError("Title cannot be blank.")
        if len(title) < 5:
            raise ValueError("Title is too short. Write something meaningful.")
        return title

    @staticmethod
    def validate_content(content: str) -> str:
        content = content.strip()
        if not content:
            raise ValueError("Notice content cannot be blank.")
        return content

    @staticmethod
    def validate_emergency_audience(notice_type, target_audience) -> None:
        """Emergency notices must target ALL — a targeted emergency defeats its purpose."""
        if (
            notice_type == Notice.Type.EMERGENCY
            and target_audience != Notice.Audience.ALL
        ):
            raise ValueError(
                "Emergency notices must target everyone (ALL). "
                "Restrict the audience only for non-emergency types."
            )

    @staticmethod
    def mark_read(notice: Notice, user) -> NoticeRead:
        """
        Records that `user` has read `notice`.

        Idempotent — calling this multiple times for the same (notice, user)
        pair is safe; get_or_create prevents duplicate rows.

        Returns the NoticeRead instance (created or existing).
        """
        obj, _ = NoticeRead.objects.get_or_create(
            notice=notice,
            user=user,
        )
        return obj
