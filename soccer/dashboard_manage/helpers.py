from .models import Club
from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError




def _parse_date_range(request):
    """
    Parses ?date_from and ?date_to from the request.
    Returns (date_from, date_to) as datetime.date objects.
    Raises ValidationError with a clear message on any problem.
    """
    raw_from = request.query_params.get("date_from")
    raw_to   = request.query_params.get("date_to")

    if not raw_from or not raw_to:
        raise ValidationError(
            {"detail": "Both date_from and date_to are required (YYYY-MM-DD)."}
        )

    try:
        date_from = date.fromisoformat(raw_from)
        date_to   = date.fromisoformat(raw_to)
    except ValueError:
        raise ValidationError(
            {"detail": "Invalid date format. Use YYYY-MM-DD."}
        )

    if date_from > date_to:
        raise ValidationError(
            {"detail": "date_from must be on or before date_to."}
        )

    return date_from, date_to


def _get_club(request):
    """
    Returns the Club that belongs to the authenticated user.
    Raises Http404 if the user has no club.
    """
    return get_object_or_404(Club, manager=request.user)


def _decimal(value):
    """Ensures a None aggregate becomes 0.00 instead of null in JSON."""
    from decimal import Decimal
    return value if value is not None else Decimal("0.00")


def _int(value):
    return value if value is not None else 0

