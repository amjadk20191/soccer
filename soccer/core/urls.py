from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CheckAvailabilityView, DeleteUserImageAPIView, RegisterUserAPIView, TestNotificationView, UserDetailView, UserDeviceView, UserLoginAPIView, ManagerLoginAPIView, UserUpdateView, NoteCreateView
from rest_framework_simplejwt.views import TokenVerifyView


urlpatterns = [
    # Custom Login & Register
    path('register/', RegisterUserAPIView.as_view(), name='register'),
    path('login/user/', UserLoginAPIView.as_view(), name='login-user'),
    path('login/manager/', ManagerLoginAPIView.as_view(), name='login-manager'),

    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('check/', CheckAvailabilityView.as_view(), name='check-availability'),
    path('users/', UserDetailView.as_view(), name='user-detail'),
    path('users/update/', UserUpdateView.as_view(), name='user-update'),
    path('users/devices/', UserDeviceView.as_view(), name='user-devices'),
    path('test-notification/', TestNotificationView.as_view(), name='test-notification'),
    path('user/image/delete/', DeleteUserImageAPIView.as_view(), name='delete-user-image'),
    path('notes/add/', NoteCreateView.as_view(), name='note-create'),
]