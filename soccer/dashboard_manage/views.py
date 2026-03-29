from wsgiref import types

from rest_framework import viewsets, mixins, permissions, parsers, exceptions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.views import APIView
from django.utils import timezone
from django.db import transaction
from datetime import date
from player_booking.models import Booking
from django.db.models import Sum
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from dashboard_manage.models import (
    BookingNumStatistics,
    BookingPriceStatistics,
    ClubEquipmentStatistics,
    ClubHourlyStatistics,
)
from collections import defaultdict


from .models import Club, ClubPricing, Pitch, Equipment, ClubEquipment, BookingDuration, PitchTypes
from .serializers import (ClubManagerSerializer, WeekdayPricingSerializer,
                        DatePricingSerializer, PitchSerializer,
                        PitchListSerializer, PitchActivationSerializer,
                        ReadEquipmentSerializer, CreateClubEquipmentSerializer, 
                        ShowClubEquipmentSerializer, BookingDurationSerializer)

class ClubManagerView(APIView):


    serializer_class = ClubManagerSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_object(self):
        club_id = self.request.auth.get('club_id')

        obj = get_object_or_404(
            Club, 
            pk=club_id, 
            manager=self.request.user
        )
        return obj
    def get(self, request):
        """Retrieve club data"""
        club = self.get_object()
        serializer = ClubManagerSerializer(club, context={'request': request})
        return Response(serializer.data)
    
    def put(self, request):
        """Full update club data"""
        club = self.get_object()
        serializer = ClubManagerSerializer(club, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def patch(self, request):
        """Partial update club data"""
        club = self.get_object()
        import json

        working_days=request.data.get('working_days',None)
        print(working_days)
        if working_days:
            working_days = json.loads(working_days)
            false_days = [int(day) for day, is_active in working_days.items() if is_active is False]
            day_off = ClubPricing.objects.filter(club_id=club.id, day_of_week__in=false_days).exists()
            if day_off:
                return Response({"error":"لا يمكن ايقاف العمل في هذا اليوم لأن هناك عرض مفعل."}, status=status.HTTP_400_BAD_REQUEST)

        
        serializer = ClubManagerSerializer(club, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BookingDurationViewSet(viewsets.ModelViewSet):
    serializer_class = BookingDurationSerializer
    def get_queryset(self):
        return BookingDuration.objects.filter(
            club_id=self.request.user.club, 
        )


class _BasePricingViewSet(viewsets.ModelViewSet):

    def get_club(self):
        try:
            return self.request.user.club 
        except AttributeError:
            raise exceptions.PermissionDenied(detail={"error": "المستخدم ليس مرتبطاً بفريق."})

    def perform_create(self, serializer):
        serializer.save(club=self.get_club())

class WeekdayPricingViewSet(_BasePricingViewSet):
    serializer_class = WeekdayPricingSerializer

    def get_queryset(self):
        return ClubPricing.objects.filter(
            club=self.get_club(), 
            type=1,
        )

class DatePricingViewSet(_BasePricingViewSet):
    serializer_class = DatePricingSerializer

    def get_queryset(self):
        now = timezone.now()
        current_date = now.date()
        return ClubPricing.objects.filter(
            club=self.get_club(), 
            type=2,
            date__gte=current_date

        )

class GetPitchesTypesView(APIView):
    def get(self, request):
        types = [
            { "name": label}
            for value, label in PitchTypes.choices
        ]
        return Response(types)

class PitchViewSet(viewsets.ModelViewSet):
    # permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        club_id = self.request.auth.get('club_id')

        return Pitch.objects.filter(club_id=club_id, is_deteted=False)

    def get_serializer_class(self):
        if self.action == 'list':
            return PitchListSerializer
        if self.action == 'set_active':
            return PitchActivationSerializer
        return PitchSerializer

    def perform_create(self, serializer):
        user = self.request.user
        club_id = getattr(user, 'club_id', None)
        if not club_id and self.request.auth:
             club_id = self.request.auth.get('club_id')
        serializer.save(club_id=club_id)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        if Booking.objects.filter(pitch=instance, status__in=[
            Booking.BookingStatus.PENDING_MANAGER,
            Booking.BookingStatus.PENDING_PAY,
            BookingStatus.COMPLETED
        ]).exists():
            return Response(
                {"error": "لا يمكن حذف الملعب لأنه مرتبط بحجوزات نشطة أو مكتملة."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.is_deteted = True
        instance.is_active = False
        instance.save(update_fields=['is_deteted', 'is_active'])

        return Response(
            {"detail": "Club equipment soft deleted successfully."},
            status=status.HTTP_200_OK
        )
    @action(detail=True, methods=['patch'], url_path='set-active')
    def set_active(self, request, pk):
        serializer = PitchActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            updated_count = self.get_queryset().filter(pk=pk).update(
                is_active=serializer.validated_data['is_active'],
                updated_at=timezone.now()
            )
           
            if not updated_count:
                return Response({"error": "الملعب غير موجود."}, status=status.HTTP_404_NOT_FOUND)

            if not self.get_queryset().filter(is_active=True).exists():
                club_id = self.request.auth.get('club_id')
                Club.objects.filter(id=club_id).update(is_active=False,
                                                    updated_at=timezone.now())
      
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
    

class EquipmentGenericsList(generics.ListAPIView):
    serializer_class = ReadEquipmentSerializer
    queryset = Equipment.objects.all()

class ClubEquipmentGenericsList(viewsets.ModelViewSet):
    serializer_class = ReadEquipmentSerializer
    
    def get_queryset(self):
        club_id = self.request.auth.get('club_id')
        
        if self.action == 'retrieve' or self.action == 'list':
            return ClubEquipment.objects.select_related('equipment').filter(club_id=club_id, is_deteted=False)
        return ClubEquipment.objects.filter(club_id=club_id, is_deteted=False)
    
    def get_serializer_class(self):
        if self.action == 'retrieve' or self.action == 'list':
            return ShowClubEquipmentSerializer
        return CreateClubEquipmentSerializer
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        instance.is_deteted = True
        instance.is_active = False
        instance.save(update_fields=['is_deteted', 'is_active'])

        return Response(
            {"detail": "Club equipment soft deleted successfully."},
            status=status.HTTP_200_OK
        )
    

##############################################statistics
##############################################statistics
##############################################statistics
"""
------------------------
4 read-only report APIs for the club owner dashboard.

All 4 views:
  - Require authentication
  - Identify the club from request.user.club (owner sees only their own data)
  - Accept ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD  (both required)
  - Return aggregated totals over the requested period
  - Return 400 if dates are missing/invalid or date_from > date_to
  - Return 404 if the authenticated user has no club

URLs (add to your urlconf):
  path("dashboard/revenue/",    RevenueReportView.as_view()),
  path("dashboard/bookings/",   BookingCountsReportView.as_view()),
  path("dashboard/hourly/",     HourlyUtilisationReportView.as_view()),
  path("dashboard/equipment/",  EquipmentSalesReportView.as_view()),
"""


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────
from .helpers import _parse_date_range, _get_club, _decimal, _int, _available_minutes_per_hour, _build_opening_map

# ─────────────────────────────────────────────────────────────
# 1. Revenue Report  — BookingPriceStatistics
# ─────────────────────────────────────────────────────────────

class RevenueReportView(APIView):
    """
    GET /dashboard/revenue/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

    Returns total money aggregated over the date range, broken down by
    booking source (owner vs player) and status (completed vs pending_pay).

    Also returns:
      - total_revenue        : completed owner + completed player
      - total_pending        : pending_pay owner + pending_pay player
      - grand_total          : all four fields summed

    Response shape:
    {
        "date_from": "2024-01-01",
        "date_to":   "2024-01-31",
        "completed": {
            "owner":  "1200.00",
            "player": "3400.00",
            "total":  "4600.00"
        },
        "pending_pay": {
            "owner":  "200.00",
            "player": "800.00",
            "total":  "1000.00"
        },
        "grand_total": "5600.00"
    }
    """
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        club = _get_club(request)
        date_from, date_to = _parse_date_range(request)

        agg = (
            BookingPriceStatistics.objects
            .filter(club=club, day__gte=date_from, day__lte=date_to)
            .aggregate(
                completed_owner=Sum("money_from_completed_owner"),
                completed_player=Sum("money_from_completed_player"),
                pending_owner=Sum("money_from_pending_pay_owner"),
                pending_player=Sum("money_from_pending_pay_player"),
            )
        )

        completed_owner  = _decimal(agg["completed_owner"])
        completed_player = _decimal(agg["completed_player"])
        pending_owner    = _decimal(agg["pending_owner"])
        pending_player   = _decimal(agg["pending_player"])

        completed_total = completed_owner + completed_player
        pending_total   = pending_owner   + pending_player
        grand_total     = completed_total + pending_total

        return Response({
            "date_from":   str(date_from),
            "date_to":     str(date_to),
            "completed": {
                "owner":  str(completed_owner),
                "player": str(completed_player),
                "total":  str(completed_total),
            },
            "pending_pay": {
                "owner":  str(pending_owner),
                "player": str(pending_player),
                "total":  str(pending_total),
            },
            "grand_total": str(grand_total),
        })


# ─────────────────────────────────────────────────────────────
# 2. Booking Counts Report  — BookingNumStatistics
# ─────────────────────────────────────────────────────────────

class BookingCountsReportView(APIView):
    """
    GET /dashboard/bookings/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

    Returns total booking counts aggregated over the date range, grouped
    into logical categories for the dashboard.

    Response shape:
    {
        "date_from": "2024-01-01",
        "date_to":   "2024-01-31",
        "completed": {
            "total":  150,
            "owner":  30,
            "player": 120
        },
        "canceled": {
            "from_completed_owner":      2,
            "from_completed_player":     8,
            "from_pending_pay_owner":    1,
            "from_pending_pay_player":   5,
            "total": 16
        },
        "pending_pay": {
            "total": 20,
            "owner": 5,
            "player": 15
        },
        "other": {
            "pending_player": 10,
            "rejected":       4,
            "no_show":        3,
            "disputed":       1,
            "expired":        7
        }
    }
    """
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        club = _get_club(request)
        date_from, date_to = _parse_date_range(request)

        agg = (
            BookingNumStatistics.objects
            .filter(club=club, day__gte=date_from, day__lte=date_to)
            .aggregate(
                completed_num=Sum("completed_num"),
                completed_num_owner=Sum("completed_num_owner"),
                canceled_completed_owner=Sum("canceled_num_from_completed_owner"),
                canceled_completed_player=Sum("canceled_num_from_completed_player"),
                canceled_pending_owner=Sum("canceled_num_from_pending_pay_owner"),
                canceled_pending_player=Sum("canceled_num_from_pending_pay_player"),
                pending_pay_num=Sum("pending_pay_num"),
                pending_pay_num_owner=Sum("pending_pay_num_owner"),
                pending_player_num=Sum("pending_player_num"),
                reject_num=Sum("reject_num"),
                no_show_num=Sum("no_Show_num"),
                disputed_num=Sum("disputed_num"),
                expired_num=Sum("expired_num"),
            )
        )

        completed_total = _int(agg["completed_num"])
        completed_owner = _int(agg["completed_num_owner"])

        can_co  = _int(agg["canceled_completed_owner"])
        can_cp  = _int(agg["canceled_completed_player"])
        can_po  = _int(agg["canceled_pending_owner"])
        can_pp  = _int(agg["canceled_pending_player"])

        pp_total = _int(agg["pending_pay_num"])
        pp_owner = _int(agg["pending_pay_num_owner"])

        return Response({
            "date_from": str(date_from),
            "date_to":   str(date_to),
            "completed": {
                "total":  completed_total,
                "owner":  completed_owner,
                "player": completed_total - completed_owner,
            },
            "canceled": {
                "from_completed_owner":    can_co,
                "from_completed_player":   can_cp,
                "from_pending_pay_owner":  can_po,
                "from_pending_pay_player": can_pp,
                "total": can_co + can_cp + can_po + can_pp,
            },
            "pending_pay": {
                "total":  pp_total,
                "owner":  pp_owner,
                "player": pp_total - pp_owner,
            },
            "other": {
                "pending_player": _int(agg["pending_player_num"]),
                "rejected":       _int(agg["reject_num"]),
                "no_show":        _int(agg["no_show_num"]),
                "disputed":       _int(agg["disputed_num"]),
                "expired":        _int(agg["expired_num"]),
            },
        })


# ─────────────────────────────────────────────────────────────
# 3. Hourly Utilisation Report  — ClubHourlyStatistics
# ─────────────────────────────────────────────────────────────
class HourlyUtilisationReportView(APIView):
    """
    GET /dashboard/hourly/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

    Available minutes per hour respects the full priority chain:
      specific-date override  >  weekday override  >  base club hours

    DB hits: 3  (down from 4)
      1. ClubOpeningTimeHistory  — base hours over time
      2. ClubPricing             — both types in one query, split in Python
      3. ClubHourlyStatistics    — booked minutes aggregated by hour + pitch

    Response shape:
    {
        "date_from": "2024-01-01",
        "date_to":   "2024-01-31",
        "days_in_range": 31,
        "by_hour": [
            {
                "hour": 8,
                "label": "08:00",
                "total_booked_minutes": 540,
                "total_available_minutes": 1860,
                "utilisation_pct": 29.0,
                "by_pitch": [
                    {"pitch_id": "...", "booked_minutes": 300},
                    {"pitch_id": "...", "booked_minutes": 240}
                ]
            },
            ...
        ]
    }
    """

    def get(self, request):
        club               = _get_club(request)
        date_from, date_to = _parse_date_range(request)
        days_in_range      = (date_to - date_from).days + 1

        # ── Queries 1 & 2: true opening window per day ────────────────────
        opening_map        = _build_opening_map(club.id, date_from, date_to)
        available_per_hour = _available_minutes_per_hour(opening_map)

        # ── Query 3: booked minutes by hour + pitch ───────────────────────
        rows = (
            ClubHourlyStatistics.objects
            .filter(club=club, date__gte=date_from, date__lte=date_to)
            .values("hour", "pitch_id")
            .annotate(booked_minutes=Sum("booked_minutes"))
            .order_by("hour", "pitch_id")
        )

        hour_map: dict = defaultdict(dict)
        for row in rows:
            hour_map[row["hour"]][str(row["pitch_id"])] = row["booked_minutes"]

        by_hour = []
        for hour in sorted(hour_map.keys()):
            pitch_data      = hour_map[hour]
            total_booked    = sum(pitch_data.values())
            pitch_count     = len(pitch_data)
            total_available = available_per_hour.get(hour, 0) * pitch_count
            utilisation     = (
                round(total_booked / total_available * 100, 1)
                if total_available > 0 else 0.0
            )
            by_hour.append({
                "hour":                    hour,
                "label":                   f"{hour:02d}:00",
                "total_booked_minutes":    total_booked,
                "total_available_minutes": total_available,
                "utilisation_pct":         utilisation,
                "by_pitch": [
                    {"pitch_id": pid, "booked_minutes": mins}
                    for pid, mins in sorted(pitch_data.items())
                ],
            })

        return Response({
            "date_from":    str(date_from),
            "date_to":      str(date_to),
            "days_in_range": days_in_range,
            "by_hour":      by_hour,
        })


# ─────────────────────────────────────────────────────────────
# 4. Equipment Sales Report  — ClubEquipmentStatistics
# ─────────────────────────────────────────────────────────────

class EquipmentSalesReportView(APIView):
    """
    GET /dashboard/equipment/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

    Returns total quantity sold and revenue earned per equipment item
    over the date range, split by owner vs player bookings.

    Response shape:
    {
        "date_from": "2024-01-01",
        "date_to":   "2024-01-31",
        "totals": {
            "quantity_by_owner":  45,
            "revenue_by_owner":   "900.00",
            "quantity_by_player": 130,
            "revenue_by_player":  "2600.00",
            "quantity_total":     175,
            "revenue_total":      "3500.00"
        },
        "by_equipment": [
            {
                "club_equipment_id": "...",
                "quantity_by_owner":  10,
                "revenue_by_owner":   "200.00",
                "quantity_by_player": 30,
                "revenue_by_player":  "600.00",
                "quantity_total":     40,
                "revenue_total":      "800.00"
            },
            ...
        ]
    }
    """
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        club = _get_club(request)
        date_from, date_to = _parse_date_range(request)

        rows = (
            ClubEquipmentStatistics.objects
            .filter(club=club, date__gte=date_from, date__lte=date_to)
            .values("club_equipment_id", "club_equipment__equipment__name")   # ← add this
            .annotate(
                qty_owner=Sum("quantity_by_ower"),      # model typo preserved
                rev_owner=Sum("revenue_by_owner"),
                qty_player=Sum("quantity_by_player"),
                rev_player=Sum("revenue_by_player"),
            )
            .order_by("club_equipment_id")
        )

        by_equipment = []
        total_qty_owner  = 0
        total_rev_owner  = _decimal(None)
        total_qty_player = 0
        total_rev_player = _decimal(None)

        for row in rows:
            qo = _int(row["qty_owner"])
            ro = _decimal(row["rev_owner"])
            qp = _int(row["qty_player"])
            rp = _decimal(row["rev_player"])

            total_qty_owner  += qo
            total_rev_owner  += ro
            total_qty_player += qp
            total_rev_player += rp

            by_equipment.append({
                "club_equipment_id": str(row["club_equipment_id"]),
                "equipment_name":    row["club_equipment__equipment__name"],   # ← add this
                "quantity_by_owner":  qo,
                "revenue_by_owner":   str(ro),
                "quantity_by_player": qp,
                "revenue_by_player":  str(rp),
                "quantity_total":     qo + qp,
                "revenue_total":      str(ro + rp),
            })

        return Response({
            "date_from": str(date_from),
            "date_to":   str(date_to),
            "totals": {
                "quantity_by_owner":  total_qty_owner,
                "revenue_by_owner":   str(total_rev_owner),
                "quantity_by_player": total_qty_player,
                "revenue_by_player":  str(total_rev_player),
                "quantity_total":     total_qty_owner + total_qty_player,
                "revenue_total":      str(total_rev_owner + total_rev_player),
            },
            "by_equipment": by_equipment,
        })
