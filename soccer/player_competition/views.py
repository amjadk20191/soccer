from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from player_team.serializers import TeamMember, MemberStatus, Team
from rest_framework import status
from .serializers import (CreateChallengeSerializer, PendingChallengeSerializer,
                           ChallengeReplySerializer, ShowChallengeTeamsSerializer,
                           RequestedChallengeSerializer)

from rest_framework.generics import ListAPIView
from .services import CreateChallengeService, ShowChallengeTeamService, GetPendingChallengesService, ReplyChallengeService, GetSentChallengesService, CancelChallengeService



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
            



class PendingChallengeListView(APIView):
    """
    GET /teams/{team_id}/challenges/pending/

    Returns all PENDING_TEAM challenges for the given team.
    Only the team captain can call this.
    """
    # permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        challenges = GetPendingChallengesService.execute(
            team_id           = team_id,
            requesting_user_id = request.user.id,
        )
        serializer = PendingChallengeSerializer(challenges, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChallengeReplyView(APIView):
    """
    POST /challenges/{challenge_id}/reply/

    Body: { "action": "accept" | "reject" }

    Only the captain of the challenged team can call this.
    """
    # permission_classes = [IsAuthenticated]

    def post(self, request, challenge_id):
        serializer = ChallengeReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        challenge = ReplyChallengeService.execute(
            challenge_id       = challenge_id,
            action             = serializer.validated_data["action"],
            requesting_user_id = request.user.id,
        )

        return Response(
            {serializer.validated_data["action"]},
            status=status.HTTP_200_OK,
        )
    



class SentChallengeListView(APIView):
    """
    GET /teams/{team_id}/challenges/sent/

    Returns all live challenges sent BY the given team.
    Only the team captain can call this.
    """

    def get(self, request, team_id):
        challenges = GetSentChallengesService.execute(
            team_id            = team_id,
            requesting_user_id = request.user.id,
        )
        serializer = RequestedChallengeSerializer(challenges, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChallengeCancelView(APIView):
    """
    POST /challenges/{challenge_id}/cancel/

    Cancels a challenge the captain's team sent.
    Only the captain of the *sending* team can call this.
    """

    def post(self, request, challenge_id):
        challenge = CancelChallengeService.execute(
            challenge_id       = challenge_id,
            requesting_user_id = request.user.id,
        )
        return Response(
            status=status.HTTP_200_OK,
        )