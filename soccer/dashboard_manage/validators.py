from django.core.exceptions import ValidationError

def validate_working_days(value):
    # 1. Must be a dict
    if not isinstance(value, dict):
        raise ValidationError(
            message="working_days must be a JSON object.",
            code="invalid_type",
            params={"received_type": type(value).__name__},
        )

    allowed_keys = {str(i) for i in range(7)}
    received_keys = set(value.keys())

    # 2. Must contain exactly keys 0–6
    if received_keys != allowed_keys:
        raise ValidationError(
            message="working_days must contain exactly the keys %(expected)s.",
            code="invalid_keys",
            params={
                "expected": sorted(allowed_keys),
                "received": sorted(received_keys),
            },
        )

    # 3. Values must be boolean
    for day, is_open in value.items():
        if not isinstance(is_open, bool):
            raise ValidationError(
                message="Value for day %(day)s must be a boolean.",
                code="invalid_value",
                params={
                    "day": day,
                    "value": is_open,
                    "value_type": type(is_open).__name__,
                },
            )
