from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterUserAPIView, UserLoginAPIView, ManagerLoginAPIView
from rest_framework_simplejwt.views import TokenVerifyView

urlpatterns = [
    # Custom Login & Register
    path('register/', RegisterUserAPIView.as_view(), name='register'),
    path('login/user/', UserLoginAPIView.as_view(), name='login-user'),
    path('login/manager/', ManagerLoginAPIView.as_view(), name='login-manager'),

    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]