from .models import User, UserDevice


def is_username_taken(username: str) -> bool:
    return User.objects.filter(username__iexact=username).exists()


def is_phone_taken(phone: str) -> bool:
    return User.objects.filter(phone=phone).exists()


class UserDeviceSelector:

    @staticmethod
    def get_user_tokens(user: User) -> list[str]:
        return list(
            UserDevice.objects.filter(user=user).values_list('fcm_token', flat=True)
        )