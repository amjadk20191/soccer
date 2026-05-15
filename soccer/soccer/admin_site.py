# soccer/admin_site.py
from django.contrib import admin
from django.utils.timezone import now
from django.urls import path
from django.shortcuts import render, get_object_or_404


STATUS_LABELS = {
    1:  ('Pending Club',      'bb'),
    2:  ('New Time Proposed', 'by'),
    3:  ('Pending Payment',   'bo'),
    4:  ('Completed',         'bg'),
    5:  ('Canceled',          'br'),
    6:  ('Rejected',          'bm'),
    7:  ('No Show',           'br'),
    8:  ('Disputed',          'br'),
    9:  ('Expired',           'bm'),
    10: ('Closed Period',     'bm'),
    11: ('Awaiting Pay',      'bo'),
    12: ('Confirming Pay',    'by'),
}


class StatsAdminSite(admin.AdminSite):
    site_header = "⚽ Soccer Platform Admin"
    site_title  = "Soccer Admin"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('clubs-overview/',
                 self.admin_view(self.clubs_overview),
                 name='clubs_overview'),
            path('clubs-overview/<uuid:club_id>/',
                 self.admin_view(self.club_detail),
                 name='club_detail'),
        ]
        return custom + urls

    # ── Club list ──────────────────────────────────────────────────
    def clubs_overview(self, request):
        from dashboard_manage.models import Club
        from player_booking.models import Booking

        clubs_qs = Club.objects.all().order_by('-created_at')
        clubs = []
        for club in clubs_qs:
            qs    = Booking.objects.filter(club=club)
            total = qs.count()
            clubs.append({
                'obj':       club,
                'total':     total,
                'completed': qs.filter(status=4).count(),
                'pending':   qs.filter(status__in=[1,2]).count(),
                'pay':       qs.filter(status__in=[3,11,12]).count(),
                'canceled':  qs.filter(status=5).count(),
                'other':     qs.filter(status__in=[6,7,8,9,10]).count(),
            })

        ctx = {
            **self.each_context(request),
            'title': 'Clubs Overview',
            'clubs': clubs,
        }
        return render(request, 'admin/clubs_overview.html', ctx)

    # ── Club detail ────────────────────────────────────────────────
    def club_detail(self, request, club_id):
        from dashboard_manage.models import Club, Pitch
        from player_booking.models import Booking

        club      = get_object_or_404(Club, pk=club_id)
        pitches_qs = Pitch.objects.filter(club=club, is_deteted=False).order_by('name')

        pitches = []
        for pitch in pitches_qs:
            bqs   = Booking.objects.filter(pitch=pitch)
            total = bqs.count()

            statuses = []
            for code, (label, css) in STATUS_LABELS.items():
                count = bqs.filter(status=code).count()
                if count > 0:
                    statuses.append({'label': label, 'css': css, 'count': count})

            recent = (
                bqs.select_related('player')
                   .order_by('-created_at')[:6]
            )
            recent_data = []
            for b in recent:
                code = b.status
                lbl, css = STATUS_LABELS.get(code, (str(code), 'bm'))
                recent_data.append({
                    'date':       b.date,
                    'start':      b.start_time,
                    'end':        b.end_time,
                    'player':     b.player.full_name if b.player else '—',
                    'price':      b.final_price,
                    'status_lbl': lbl,
                    'status_css': css,
                })

            pitches.append({
                'obj':      pitch,
                'total':    total,
                'statuses': statuses,
                'recent':   recent_data,
            })

        ctx = {
            **self.each_context(request),
            'title':   f'{club.name} — Pitches',
            'club':    club,
            'pitches': pitches,
        }
        return render(request, 'admin/club_detail.html', ctx)

    # ── Dashboard index ────────────────────────────────────────────
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        today = now().date()

        try:
            from core.models import User
            extra_context["total_users"]     = User.objects.count()
            extra_context["users_today"]     = User.objects.filter(created_at__date=today).count()
            extra_context["new_users_today"] = (
                User.objects.filter(created_at__date=today).order_by("-created_at")[:10]
            )
        except Exception:
            extra_context.setdefault("total_users",     "—")
            extra_context.setdefault("users_today",     "—")
            extra_context.setdefault("new_users_today", [])

        try:
            from player_booking.models import Booking
            qs = Booking.objects.all()
            extra_context["total_bookings"]     = qs.count()
            extra_context["bookings_today"]     = qs.filter(created_at__date=today).count()
            extra_context["recent_bookings"]    = qs.select_related("pitch__club").order_by("-created_at")[:10]
            extra_context["status_completed"]   = qs.filter(status=4).count()
            extra_context["status_pending"]     = qs.filter(status__in=[1,2]).count()
            extra_context["status_pending_pay"] = qs.filter(status__in=[3,11,12]).count()
            extra_context["status_canceled"]    = qs.filter(status=5).count()
            extra_context["status_rejected"]    = qs.filter(status__in=[6,7,8,9,10]).count()
        except Exception:
            for k in ["total_bookings","bookings_today","status_completed",
                      "status_pending","status_pending_pay","status_canceled","status_rejected"]:
                extra_context.setdefault(k, "—")
            extra_context.setdefault("recent_bookings", [])

        try:
            from dashboard_manage.models import Club
            extra_context["total_clubs"] = Club.objects.filter(is_active=True).count()
        except Exception:
            extra_context.setdefault("total_clubs", "—")

        try:
            from player_team.models import Team
            extra_context["total_teams"] = Team.objects.filter(is_active=True).count()
        except Exception:
            extra_context.setdefault("total_teams", "—")

        return super().index(request, extra_context=extra_context)


admin.site.__class__ = StatsAdminSite
admin.site.site_header = "⚽ Soccer Platform Admin"
admin.site.site_title  = "Soccer Admin"
admin.site.index_title = "Dashboard"