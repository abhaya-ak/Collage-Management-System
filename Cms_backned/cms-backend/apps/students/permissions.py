"""Permission map (action -> permission code) for the students viewset."""

STUDENT_PERMISSIONS = {
    "list": "view_student",
    "retrieve": "view_student",
    "update": "update_student",
    "partial_update": "update_student",
    "admission": "admit_student",
    "promote": "promote_student",
    "enroll": "manage_enrollment",
    "change_section": "manage_enrollment",
}
