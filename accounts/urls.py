from django.urls import path
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import ChangePasswordView, CurrentUserView, RegisterUserView

urlpatterns = [
    path("register/", RegisterUserView.as_view(), name="auth-register"),
    path("login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="auth-logout"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("users/me/", CurrentUserView.as_view(), name="auth-current-user"),
]
