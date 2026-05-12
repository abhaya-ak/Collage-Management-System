from django.urls import path
from .views import UsernameLoginView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('login/', UsernameLoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]