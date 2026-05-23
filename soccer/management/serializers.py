from core.governorates import SyrianGovernorate   
from rest_framework import serializers
from .models import ClubPayout



class ClubRevenueFilterSerializer(serializers.Serializer):
    date_from   = serializers.DateField()
    date_to     = serializers.DateField()
    club_name   = serializers.CharField(required=False, allow_blank=False)
    governorate = serializers.ChoiceField(
        choices=[(g.value, g.label) for g in SyrianGovernorate],
        required=False,
    )

    def validate(self, attrs):
        if attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError(
                {"error": "يجب أن يكون تاريخ البداية قبل تاريخ النهاية."}
            )
        return attrs


class RecordPayoutSerializer(serializers.Serializer):
    club_id = serializers.UUIDField()
    amount  = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1)
    date    = serializers.DateField()
    notes   = serializers.CharField(required=False, allow_blank=True, default='')


class ClubPayoutFilterSerializer(serializers.Serializer):
    club_name   = serializers.CharField(required=False, allow_blank=False)
    governorate = serializers.IntegerField(required=False)
    date_from   = serializers.DateField(required=False)   # ← add
    date_to     = serializers.DateField(required=False)   # ← add

    def validate(self, attrs):
        df = attrs.get('date_from')
        dt = attrs.get('date_to')
        if df and dt and df > dt:
            raise serializers.ValidationError(
                {"date_from": "يجب أن يكون تاريخ البداية قبل تاريخ النهاية."}
            )
        return attrs