from .models import User


def is_username_taken(username: str) -> bool:
    return User.objects.filter(username__iexact=username).exists()


def is_phone_taken(phone: str) -> bool:
    return User.objects.filter(phone=phone).exists()