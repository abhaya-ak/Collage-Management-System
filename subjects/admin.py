from django.contrib import admin
from auth_core.admin_base import RBACAdmin
from subjects.models import Subject


@admin.register(Subject)
class SubjectAdmin(RBACAdmin):
    add_permission    = "subjects.manage_subject"
    change_permission = "subjects.manage_subject"
    delete_permission = "subjects.manage_subject"

    list_display   = ["code", "name", "faculty", "teacher", "full_marks", "pass_marks"]
    list_filter    = ["faculty"]
    search_fields  = ["code", "name", "teacher__user__first_name", "faculty__name"]
    ordering       = ["faculty", "name"]
    readonly_fields = ["created_at", "updated_at"]
