"""Permission maps (action -> permission code) for exam/result viewsets."""

EXAM_PERMISSIONS = {
    "list": "view_exam",
    "retrieve": "view_exam",
    "create": "manage_exam",
    "update": "manage_exam",
    "partial_update": "manage_exam",
    "destroy": "manage_exam",
}

EXAM_SCHEDULE_PERMISSIONS = {
    "list": "view_exam_schedule",
    "retrieve": "view_exam_schedule",
    "create": "manage_exam_schedule",
    "update": "manage_exam_schedule",
    "partial_update": "manage_exam_schedule",
    "destroy": "manage_exam_schedule",
}

MARK_PERMISSIONS = {
    "list": "view_marks",
    "retrieve": "view_marks",
    "enter": "enter_marks",
}

RESULT_PERMISSIONS = {
    "list": "view_result",
    "retrieve": "view_result",
    "generate": "generate_result",
    "publish": "publish_result",
}
