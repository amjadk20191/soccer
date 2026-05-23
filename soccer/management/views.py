from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services.ClubPayoutService import get_clubs_payout_summary, record_payout
from .serializers import (
    RecordPayoutSerializer,
    ClubPayoutFilterSerializer,
)
from .serializers import ClubRevenueFilterSerializer
from .services.ClubRevenueService import get_clubs_revenue


class ClubRevenueView(APIView):

    def get(self, request):
        serializer = ClubRevenueFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        data = get_clubs_revenue(
            date_from   = serializer.validated_data['date_from'],
            date_to     = serializer.validated_data['date_to'],
            club_name   = serializer.validated_data.get('club_name'),
            governorate = serializer.validated_data.get('governorate'),
        )

        return Response(data, status=status.HTTP_200_OK)
    




class ClubPayoutSummaryView(APIView):
    """
    GET  /api/management/club-payouts/
        ?club_name=  &governorate=
    Returns all clubs with collected / sent / owed amounts.
    """

    def get(self, request):
        serializer = ClubPayoutFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        data = get_clubs_payout_summary(
            club_name   = d.get('club_name'),
            governorate = d.get('governorate'),
            date_from   = d.get('date_from'),    # ← add
            date_to     = d.get('date_to'),      # ← add
        )
        return Response(data, status=status.HTTP_200_OK)

class RecordPayoutView(APIView):
    """
    POST /api/management/club-payouts/record/
    Body: { club_id, amount, date, notes }
    Records a new transfer from MATCH to a club.
    """

    def post(self, request):
        serializer = RecordPayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        payout = record_payout(
            club_id    = d['club_id'],
            amount     = d['amount'],
            date       = d['date'],
            notes      = d.get('notes', ''),
            done_by = request.user,
        )
        return Response({'payout_id': str(payout.id)}, status=status.HTTP_201_CREATED)