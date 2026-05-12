from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import UsernameTokenObtainPairSerializer

class UsernameLoginView(TokenObtainPairView):
    serializer_class = UsernameTokenObtainPairSerializer