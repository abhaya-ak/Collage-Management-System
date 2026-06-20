"""Permission map (action -> permission code) for the attendance viewset."""

ATTENDANCE_PERMISSIONS = {
    "list": "view_attendance",
    "retrieve": "view_attendance",
    "create": "mark_attendance",
    "mark": "mark_attendance",
    "lock": "mark_attendance",
}
