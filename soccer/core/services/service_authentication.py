from rest_framework_simplejwt.serializers import TokenObtainPairSerializer





class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['role'] = user.role
        if user.role ==2:
            token["club_id"] = str(user.club.id)
        return token