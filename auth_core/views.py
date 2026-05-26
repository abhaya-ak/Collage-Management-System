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
)
from auth_core.services.auth_service import AuthService
from auth_core.services.audit_service import AuditService
from auth_core.services.rbac_service import RBACService
from auth_core.services.session_service import SessionService

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
