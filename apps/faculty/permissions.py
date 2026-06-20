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

LEAVE_PERMISSIONS = {
    "list": "view_leave",
    "retrieve": "view_leave",
    "create": "manage_leave",
    "approve": "manage_leave",
    "reject": "manage_leave",
}
