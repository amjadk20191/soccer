from .. import selectors


FIELD_CHECKERS = {
    'username': selectors.is_username_taken,
    'phone': selectors.is_phone_taken,
}


def check_field_availability(username: str, phone: str) -> dict:
    return {
        'username': not selectors.is_username_taken(username),
        'phone': not selectors.is_phone_taken(phone),
    }