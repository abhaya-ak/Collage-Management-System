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
    # student self-service (scoped to request.user's own record)
    "me": "view_own_profile",
    "my_attendance": "view_own_attendance",
    "my_routine": "view_routine",
    "my_teachers": "view_own_teachers",
    "my_teacher_leaves": "view_teacher_leave",
    "my_academic_leaves": "view_own_academic_leave",
    "my_fees": "view_own_fee",
}
