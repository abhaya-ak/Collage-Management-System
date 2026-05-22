# auth_core/admin.py
from django.contrib import admin
from auth_core.models import UserProfile, UserSession, TokenBlacklist, AuditLog


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'phone', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'jti_short', 'ip_address', 'is_active', 'created_at', 'closed_at']
    list_filter   = ['is_active']
    search_fields = ['user__username', 'jti', 'ip_address']
    readonly_fields = ['jti', 'ip_address', 'user_agent', 'created_at', 'last_seen_at']

    @admin.display(description='JTI (prefix)')
    def jti_short(self, obj):
        return f"{obj.jti[:12]}…"


@admin.register(TokenBlacklist)
class TokenBlacklistAdmin(admin.ModelAdmin):
    list_display  = ['jti_short', 'blacklisted_at', 'expires_at']
    readonly_fields = ['jti', 'blacklisted_at', 'expires_at']

    @admin.display(description='JTI (prefix)')
    def jti_short(self, obj):
        return f"{obj.jti[:12]}…"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ['event', 'user', 'ip_address', 'created_at']
    list_filter   = ['event']
    search_fields = ['user__username', 'ip_address', 'event']
    readonly_fields = ['user', 'event', 'ip_address', 'user_agent', 'metadata', 'created_at']

    def has_add_permission(self, request):
        return False  # Audit logs are immutable — never add via admin

    def has_change_permission(self, request, obj=None):
        return False  # Immutable
