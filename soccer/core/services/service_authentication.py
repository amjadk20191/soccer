from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from dashboard_manage.models import ClubStaff




class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['role'] = user.role
        if user.role ==2:
            token["club_id"] = str(user.club.id)
        if user.role == 4:
            token["club_id"] = str(ClubStaff.objects.values('club_id').filter(user=user.id).first()['club_id'])
        return token