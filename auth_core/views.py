# auth_core/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.parsers import JSONParser, MultiPartParser

from auth_core.models import AuditLog, UserProfile
from auth_core.serializers import (
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    UserProfileSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)
from auth_core.services.auth_service import AuthService
from auth_core.services.audit_service import AuditService
from auth_core.services.rbac_service import RBACService
from auth_core.services.session_service import SessionService
from auth_core.services.password_reset_service import PasswordResetService

def _user_response(user) -> dict:
    """Compact user object returned with every token response."""
    return {
        'id':         user.pk,
        'username':   user.username,
        'email':      user.email,
        'first_name': user.first_name,
        'last_name':  user.last_name,
        'role':       RBACService.get_role(user),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/register/
# ─────────────────────────────────────────────────────────────────────────────
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny] # it allow all type of users 

    def post(self, request):
        serializer = RegisterSerializer(data=request.data) # register serializers call 
        serializer.is_valid(raise_exception=True) # is valied x ki xaina check hun x

        result = AuthService.register(serializer.validated_data, request=request) # authservieces.reister()

        return Response(
            {
                'access':  result['access'],
                'refresh': result['refresh'],
                'user':    _user_response(result['user']),
            },
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/login/
# ─────────────────────────────────────────────────────────────────────────────
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.login(
            username = serializer.validated_data['username'],
            password = serializer.validated_data['password'],
            request  = request,
        )

        return Response(
            {
                'access':  result['access'],
                'refresh': result['refresh'],
                'user':    _user_response(result['user']),
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/logout/
# ─────────────────────────────────────────────────────────────────────────────
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': "'refresh' token is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        AuthService.logout(
            refresh_token = refresh_token,
            request       = request,
            user          = request.user,
        )
        return Response(
            {'detail': 'Successfully logged out.'},
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/refresh/
# ─────────────────────────────────────────────────────────────────────────────

class RefreshView(APIView):
    """
    Secure token rotation — blacklists old refresh token, issues new pair.
    This replaces simplejwt's raw TokenRefreshView.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': "'refresh' token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = AuthService.refresh(refresh_token=refresh_token, request=request)

        return Response(
            {'access': result['access'], 'refresh': result['refresh']},
            status=status.HTTP_200_OK,
        )

class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [JSONParser, MultiPartParser]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(
            profile,
            data    = request.data,
            partial = True,
            context = {'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/change-password/
# ─────────────────────────────────────────────────────────────────────────────
class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Incorrect current password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        # Immediately revoke ALL active sessions for this user.
        # Without this, any stolen refresh token (7-day lifetime) remains valid
        # even after the password is changed — the attacker keeps access.
        # This includes the current session, so the client must re-login.
        SessionService.close_all_for_user(user)

        AuditService.log(
            event   = AuditLog.Event.PASSWORD_CHANGE,
            user    = user,
            request = request,
        )

        return Response({
            'detail': 'Password changed successfully. Please log in again with your new password.',
        })


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/forgot-password/
# ─────────────────────────────────────────────────────────────────────────────
class ForgotPasswordView(APIView):
    """
    POST /api/v1/auth/forgot-password/

    Accepts an email address and — if an active account exists — sends a
    one-time reset link valid for 60 minutes.

    Always returns HTTP 200 regardless of whether the email is registered.
    This prevents user-enumeration attacks: an attacker cannot distinguish
    "email not found" from "email sent".
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        PasswordResetService.request_reset(
            email   = serializer.validated_data['email'],
            request = request,
        )

        return Response(
            {'detail': 'If an account with that email exists, a reset link has been sent.'},
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/reset-password/
# ─────────────────────────────────────────────────────────────────────────────
class ResetPasswordView(APIView):
    """
    POST /api/v1/auth/reset-password/

    Validates the token from the email link and sets the new password.
    On success: all active sessions are revoked — the user must log in again.
    Returns 400 with a descriptive message on any invalid / expired token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            PasswordResetService.confirm_reset(
                token_str    = serializer.validated_data['token'],
                new_password = serializer.validated_data['new_password'],
                request      = request,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {'detail': 'Password reset successful. Please log in with your new password.'},
            status=status.HTTP_200_OK,
        )
