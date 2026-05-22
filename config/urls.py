# config/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Auth (register / login / logout / refresh / me / change-password) ──
    # All JWT logic handled by auth_core — no raw simplejwt views exposed.
    path('api/v1/auth/', include('auth_core.urls')),

    # ── Domain apps ────────────────────────────────────────────────────────
    path('api/v1/students/',   include('students.urls')),
    path('api/v1/academics/',  include('academics.urls')),
    path('api/v1/attendance/', include('attendance.urls')),
    path('api/v1/notices/',    include('notices.urls')),
    path('api/v1/feedback/',   include('feedback.urls')),
    path('api/v1/subjects/',   include('subjects.urls')),
    path('api/v1/fees/',       include('fees.urls')),
]