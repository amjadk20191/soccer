from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/dashboard/booking/', include('dashboard_booking.urls')),
    path('api/dashboard/manage/', include('dashboard_manage.urls')),
    path('api/dashboard/statistics/', include('dashboard_statistics.urls')),
    path('api/management/', include('management.urls')),
    path('api/player/booking/', include('player_booking.urls')),
    path('api/player/competition/', include('player_competition.urls')),
    path('api/player/manage/', include('player_manage.urls')),
    path('api/player/statistics/', include('player_statistics.urls')),
    path('api/player/team/', include('player_team.urls')),

]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )