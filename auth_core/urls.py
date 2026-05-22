# auth_core/urls.py
from django.urls import path

from auth_core.views import (
    RegisterView,
    LoginView,
    LogoutView,
    RefreshView,
    MeView,
    ChangePasswordView,
)

urlpatterns = [
    # POST /api/v1/auth/register/       — create account (default role: student)
    path('register/',        RegisterView.as_view(),       name='auth_register'),

    # POST /api/v1/auth/login/          — returns access + refresh tokens
    path('login/',           LoginView.as_view(),          name='auth_login'),

    # POST /api/v1/auth/logout/         — blacklists refresh token, closes session
    path('logout/',          LogoutView.as_view(),         name='auth_logout'),

    # POST /api/v1/auth/refresh/        — rotates token pair (blacklists old)
    path('refresh/',         RefreshView.as_view(),        name='auth_refresh'),

    # GET  /api/v1/auth/me/             — current user profile + role + permissions
    # PATCH /api/v1/auth/me/            — update avatar, phone, bio
    path('me/',              MeView.as_view(),             name='auth_me'),

    # POST /api/v1/auth/change-password/ — old + new password
    path('change-password/', ChangePasswordView.as_view(), name='auth_change_password'),
]
