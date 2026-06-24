"""
Permission maps (action -> permission code) for academics viewsets.
Consumed by shared.permissions.ActionPermission.
"""


def _crud(entity: str) -> dict:
    """Standard view/create/update/delete map for an entity."""
    return {
        "list": f"view_{entity}",
        "retrieve": f"view_{entity}",
        "create": f"create_{entity}",
        "update": f"update_{entity}",
        "partial_update": f"update_{entity}",
        "destroy": f"delete_{entity}",
    }


def _view_manage(entity: str) -> dict:
    """view_<entity> for reads, manage_<entity> for all writes."""
    return {
        "list": f"view_{entity}",
        "retrieve": f"view_{entity}",
        "create": f"manage_{entity}",
        "update": f"manage_{entity}",
        "partial_update": f"manage_{entity}",
        "destroy": f"manage_{entity}",
    }


ACADEMIC_YEAR_PERMISSIONS = _crud("academic_year")
PROGRAM_PERMISSIONS = _crud("program")
SEMESTER_PERMISSIONS = _crud("semester")
SUBJECT_PERMISSIONS = _crud("subject")
SECTION_PERMISSIONS = {
    **_view_manage("section"),
    "capacity": "view_section",   # Phase 4 — capacity dashboard
}
CURRICULUM_PERMISSIONS = _view_manage("curriculum")
ROUTINE_PERMISSIONS = _view_manage("routine")
ACADEMIC_LEAVE_PERMISSIONS = _view_manage("academic_leave")

