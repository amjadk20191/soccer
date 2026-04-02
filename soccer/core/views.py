from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserRegistrationSerializer, LoginSerializer
from core.services.service_authentication import MyTokenObtainPairSerializer
from .serializers import CheckAvailabilityInputSerializer, CheckAvailabilityOutputSerializer
from .services.validateusername_phone import check_field_availability


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


class CheckAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        input_serializer = CheckAvailabilityInputSerializer(data=request.query_params)
        input_serializer.is_valid(raise_exception=True)

        data = input_serializer.validated_data
        result = check_field_availability(data['username'], data['phone'])

        
        return Response(result)


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

        if user.role != 2:
            return Response(
                {"error": "الوصول مرفوض."},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = MyTokenObtainPairSerializer.get_token(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            # 'role': user.role,
        }, status=status.HTTP_200_OK)