"""Auth routes -> mounted at /api/auth/ by config.urls."""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    SetRolesView,
    UserCreateView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("users/", UserCreateView.as_view(), name="user-create"),
    path("users/<uuid:pk>/set-roles/", SetRolesView.as_view(), name="user-set-roles"),
]