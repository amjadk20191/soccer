from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re


def validate_phone_format(value: str) -> None:
    if not re.match(r'^09\d{8}$', value):
        raise ValidationError(
            {'phone': 'رقم الهاتف يجب أن يبدأ بـ 09 ويتكون من 10 أرقام.'},
            
        )