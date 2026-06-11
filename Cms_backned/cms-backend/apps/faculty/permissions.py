"""Permission map (action -> permission code) for the faculty viewset."""

FACULTY_PERMISSIONS = {
    "list": "view_faculty",
    "retrieve": "view_faculty",
    "create": "manage_faculty",
    "update": "manage_faculty",
    "partial_update": "manage_faculty",
    "assign_subject": "assign_subject",
    "update_assignment": "assign_subject",
    "remove_assignment": "assign_subject",
}
