from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .services.notification_service import NotificationService
from .serializers import UserDeviceSerializer, UserRegistrationSerializer, LoginSerializer, NoteSerializer
from core.services.service_authentication import MyTokenObtainPairSerializer
from .serializers import CheckAvailabilityInputSerializer,UserSerializer,UpdateUserSerializer
from .services.validateusername_phone import check_field_availability
from .services.UserServices import UserService, UserDeviceService
from .models import User


class RegisterUserAPIView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = MyTokenObtainPairSerializer.get_token(user)


        return Response({
            "user": serializer.data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user, context={'request': request}).data)

class UserUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UpdateUserSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_user = UserService.update_user(request.user, serializer.validated_data)
        return Response(UserSerializer(updated_user, context={'request': request}).data)

class UserDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        UserDeviceService.register_device(request.user, serializer.validated_data['fcm_token'])
        return Response({'detail': 'Device registered successfully.'}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        serializer = UserDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        UserDeviceService.remove_device(request.user, serializer.validated_data['fcm_token'])
        return Response({'detail': 'Device removed successfully.'}, status=status.HTTP_204_NO_CONTENT)

class TestNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        NotificationService.send_notification(
            user=request.user,
            title=request.data.get('title', 'Test'),
            body=request.data.get('body', 'Test notification'),
        )
        return Response({'detail': 'Notification sent.'})

class DeleteUserImageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        UserService.delete_user_image(request.user)
        return Response(
            {'detail': 'تم حذف الصورة وإعادة تعيينها إلى الافتراضية.'},
            status=status.HTTP_200_OK
        )

class CheckAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        input_serializer = CheckAvailabilityInputSerializer(data=request.query_params)
        input_serializer.is_valid(raise_exception=True)

        data = input_serializer.validated_data
        result = check_field_availability(data['username'], data['phone'])

        
        return Response(result)



class NoteCreateView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = request.user.role
        # role = request.auth.payload.get('role')
        note = serializer.save(user=request.user, role=role)

        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)
# class NoteCreateView(APIView):

#     def post(self, request):
#         serializer = NoteSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         # Get user from token
#         from django.contrib.auth import get_user_model
#         User = get_user_model()
#         user_id = request.auth.payload.get('user_id')
#         role = request.auth.payload.get('role')

#         try:
#             user = User.objects.get(pk=user_id)
#         except User.DoesNotExist:
#             return Response(
#                 {'error': 'المستخدم غير موجود.'},
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         note = serializer.save(user=user, role=role)
#         return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)

class UserLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        if user.role != 1:
            return Response(
                {"error": "وصول غير مصرح به. هذا الحساب لا يملك صلاحيات الدخول."},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = MyTokenObtainPairSerializer.get_token(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            # 'user_id': user.id,
            # 'role': user.role,
        }, status=status.HTTP_200_OK)

class ManagerLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        if user.role not in (2, 4):
            return Response(
                {"error": "الوصول مرفوض."},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = MyTokenObtainPairSerializer.get_token(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': user.role,
        }, status=status.HTTP_200_OK)