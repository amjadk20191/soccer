from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from player_team.serializers import TeamMember, MemberStatus, Team
from rest_framework import status
from .serializers import (CreateChallengeSerializer, PendingChallengeSerializer,
                           ChallengeReplySerializer, ShowChallengeTeamsSerializer,
                           RequestedChallengeSerializer, ChallengeDetailSerializer,
                           PlayerProfileSerializer, TeamDetailSerializer)

from rest_framework.generics import ListAPIView
from .services import CreateChallengeService, ShowChallengeTeamService, GetPendingChallengesService, ReplyChallengeService, GetSentChallengesService, CancelChallengeService
from rest_framework import generics

from .services.player_profile_service import PlayerProfileService
from .services.team_detail_service import TeamDetailService
from django.db import transaction
from .services.challenge_detail_service import ChallengeDetailService
from .services.challenge_equipment_service import ChallengeEquipmentService


class ChallengeDetailView(generics.RetrieveAPIView):
    serializer_class   = ChallengeDetailSerializer

    def get_object(self):
        return ChallengeDetailService.get_challenge_detail(
            challenge_id=self.kwargs['challenge_id']
        )

class TeamDetailView(generics.RetrieveAPIView):
    serializer_class   = TeamDetailSerializer

    def get_object(self):
        return TeamDetailService.get_team_detail(
            team_id=self.kwargs['team_id']
        )
    
class PlayerProfileView(generics.RetrieveAPIView):
    serializer_class   = PlayerProfileSerializer

    def get_object(self):
        return PlayerProfileService.get_player_profile(
            player_id=self.kwargs['player_id']
        )
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
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # 1. Initialize the serializer with the incoming JSON data
        serializer = CreateChallengeSerializer(data=request.data)
        
        # 2. Validate basic types and dates (from your serializer)
        serializer.is_valid(raise_exception=True)
        equipments = serializer.validated_data.pop("equipments", None)
        # try:
        # 3. Pass to your Service Layer

        challenge = CreateChallengeService.create(
            validated_data=serializer.validated_data,
            requesting_user_id=request.user.id
        )
        if equipments:
            ChallengeEquipmentService.create_challenge_equipments(
                challenge=challenge,
                equipments=equipments,
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