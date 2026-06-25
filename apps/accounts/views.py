"""
Sprint 4 — Step 4: Authentication APIs (thin views; logic lives in services).

    POST /api/auth/login/            -> obtain access + refresh tokens
    POST /api/auth/refresh/          -> (SimpleJWT TokenRefreshView, wired in urls)
    POST /api/auth/logout/           -> blacklist refresh token
    GET  /api/auth/me/               -> current user
    POST /api/auth/change-password/  -> change own password
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission

from apps.accounts.models import CustomUser
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    CreateUserSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    SetRolesSerializer,
    UserSerializer,
)
from shared.responses import error_response, success_response


class IsSuperUser(BasePermission):
    message = "Only a superuser can manage users and roles."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def _tokens_for(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = services.authenticate_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        data = {
            "tokens": _tokens_for(user),
            "user": UserSerializer(user).data,
            "must_change_password": user.must_change_password,
        }
        return success_response(data=data, message="Login successful.")


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return error_response(
                message="Refresh token is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return error_response(
                message="Invalid or expired refresh token.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return success_response(message="Logout successful.")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(
            data=UserSerializer(request.user).data,
            message="Current user.",
        )

    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.update_profile(request.user, serializer.validated_data)
        return success_response(
            data=UserSerializer(user).data,
            message="Profile updated successfully.",
        )


class UserCreateView(APIView):
    """POST /api/auth/users/ — superuser creates a user (e.g. an Admin) with roles."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.create_user_with_roles(
            actor=request.user, **serializer.validated_data
        )
        return success_response(
            data=UserSerializer(user).data,
            message="User created successfully.",
            status_code=201,
        )


class SetRolesView(APIView):
    """POST /api/auth/users/<id>/set-roles/ — superuser replaces a user's roles."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, pk):
        target = get_object_or_404(CustomUser.objects.all(), pk=pk)
        serializer = SetRolesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.set_roles(
            target, serializer.validated_data["roles"], actor=request.user
        )
        return success_response(
            data=UserSerializer(user).data,
            message="Roles updated successfully.",
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        services.change_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return success_response(message="Password changed successfully.")
