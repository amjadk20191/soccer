import json

from django.http import JsonResponse
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView, View, csrf_exempt
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from core.governorates import SyrianGovernorate

from .services.notification_service import NotificationService
from .serializers import NotificationSerializer, UserDeviceSerializer, UserRegistrationSerializer, LoginSerializer, NoteSerializer
from core.services.service_authentication import MyTokenObtainPairSerializer
from .serializers import CheckAvailabilityInputSerializer,UserSerializer,UpdateUserSerializer
from .services.validateusername_phone import check_field_availability
from .services.UserServices import UserService, UserDeviceService
from .models import AppVersion, Notification, User
from typing import Any, Dict, List, Tuple, Optional
from django.utils.decorators import method_decorator

from .pagination import NotificationPagination


class SyrianGovernorateListAPI(APIView):
    def get(self, request):
        data = [
                {"value": choice.value, "label": choice.label}
                for choice in SyrianGovernorate
            ]
        return Response(data)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        queryset = (
            Notification.objects
            .filter(user=self.request.user)
            .only(
                'id',
                'title',
                'message',
                'is_read',
                'notification_type',
                'helper_id',
                'created_at',
            )
            .order_by('-created_at')
        )

        # filter unread only
        unread_only = self.request.query_params.get('unread')

        if unread_only == 'true':
            queryset = queryset.filter(is_read=False)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)

        unread_ids = [
            n.id for n in page if not n.is_read
        ]
        serializer = self.get_serializer(page, many=True)

        if unread_ids:
            Notification.objects.filter(
                id__in=unread_ids
            ).update(is_read=True)



        return self.get_paginated_response(serializer.data)
    


class UnreadNotificationCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        return Response({
            'unread_count': unread_count
        })



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




class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = Notification.objects.filter(
            id=notification_id,
            user=request.user
        ).first()

        if not notification:
            return Response({'error': 'not found'}, status=404)

        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'detail': 'marked as read'})


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        return Response({'detail': 'all marked as read'})

class GenericApiView(View):
    """
    Generic base for JSON API views.
    Handles parsing, validation, and response formatting.
    """
    
    http_method_names = ["post"]
    required_fields: List[str] = []
    choice_validators: Dict[str, Tuple[str, ...]] = {}
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def parse_body(self, request) -> Dict[str, Any]:
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            self.error("Invalid JSON")
    
    def validate_required(self, body: Dict[str, Any]) -> None:
        for field in self.required_fields:
            if field not in body or not body[field]:
                self.error(f"'{field}' is required")
    
    def validate_choices(self, body: Dict[str, Any]) -> None:
        for field, valid in self.choice_validators.items():
            value = body.get(field, "").lower()
            if value not in valid:
                self.error(f"'{field}' must be one of {list(valid)}")
            body[field] = value
    
    def error(self, message: str, status: int = 400):
        response = JsonResponse({"error": message}, status=status)
        raise ApiException(response)


class ApiException(Exception):
    """Raised to abort and return an error response."""
    def __init__(self, response: JsonResponse):
        self.response = response


class VersionCheckView(GenericApiView):
    """
    POST /api/v1/version-check/
    
    Generic view with declarative validation.
    """
    
    required_fields = ["current_version", "platform", "app_type"]
    choice_validators = {
        "platform": ("android", "ios"),
        "app_type": ("admin", "user"),
    }
    
    def post(self, request):
        body = self.parse_body(request)
        self.validate_required(body)
        self.validate_choices(body)
        
        current_version = body["current_version"]
        current_build = body.get("build_number", 0)
        platform = body["platform"]
        app_type = body["app_type"]
        
        latest = self.get_latest_version(app_type, platform)
        
        if not latest:
            return self.no_update_response(current_version)
        
        update_available = self.is_newer(
            current_version, current_build, latest
        )
        
        return JsonResponse({
            "update_available": update_available,
            "is_required": latest.is_required if update_available else False,
            "latest_version": latest.version,
            "download_url": latest.download_url if update_available else "",
            "release_notes": latest.release_notes if update_available else "",
            "is_maintenance": latest.is_maintenance,  # <-- ADDED
        })

    
    def get_latest_version(self, app_type: str, platform: str) -> Optional[AppVersion]:
        try:
            return AppVersion.objects.filter(
                app_type=app_type,
                platform=platform,
                is_active=True,
            ).latest("created_at")
        except AppVersion.DoesNotExist:
            return None
    
    def no_update_response(self, current_version: str) -> JsonResponse:
        return JsonResponse({
            "update_available": False,
            "is_required": False,
            "latest_version": current_version,
            "download_url": "",
            "release_notes": "",
        })
    
    def is_newer(self, current: str, current_build: int, latest: AppVersion) -> bool:
        def parse(v: str) -> List[int]:
            parts = v.split(".")
            return [int(p) if p.isdigit() else 0 for p in parts] + [0] * (3 - len(parts))
        
        current_parsed = parse(current)
        latest_parsed = parse(latest.version)
        
        if latest_parsed > current_parsed:
            return True
        if latest_parsed < current_parsed:
            return False
        
        return latest.build_number > current_build

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
            'full_name': user.full_name,
            'username': user.username,
            'phone': user.phone,
            'birthday': user.birthday,
            'height': user.height,
            'weight': user.weight,
            'foot_preference': user.foot_preference,
            'booking_time': user.booking_time,
            'challenge_time': user.challenge_time,
            'cancel_time': user.cancel_time,
            'image': request.build_absolute_uri(user.image.url) if user.image else None,
            'governorate': user.get_governorate_display()

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