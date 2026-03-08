from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from player_team.serializers import TeamMember, MemberStatus, Team
from rest_framework import status
from .serializers import CreateChallengeSerializer
from .services import CreateChallengeService

from rest_framework.generics import ListAPIView

from .serializers import ShowChallengeTeamsSerializer
from .services import ShowChallengeTeamService


class ChallengeTeamsView(ListAPIView):
    serializer_class = ShowChallengeTeamsSerializer

    def get_queryset(self):
        return ShowChallengeTeamService.get_challenge_teams(
            self.kwargs['team_id'], self.request.user.id)
    



class CreateChallengeAPIView(APIView):
    """
    POST API to create a new match challenge between two teams.
    """
    # Ensure only logged-in users can hit this endpoint
    # permission_classes = [IsAuthenticated] 

    def post(self, request, *args, **kwargs):
        # 1. Initialize the serializer with the incoming JSON data
        serializer = CreateChallengeSerializer(data=request.data)
        
        # 2. Validate basic types and dates (from your serializer)
        serializer.is_valid(raise_exception=True)
        # try:
        # 3. Pass to your Service Layer
        challenge = CreateChallengeService.create(
            validated_data=serializer.validated_data,
            requesting_user_id=request.user.id
        )
        
        # 4. Return Success Response
        return Response(
            {
                "message": "Challenge sent successfully!",
                "challenge_id": challenge.id
            }, 
            status=status.HTTP_201_CREATED
        )
        

        # except Exception as e:
        #     # Catch-all for unexpected crashes (database down, etc.)
        #     return Response(
        #         {"error": "An unexpected error occurred processing your challenge."}, 
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
            
        