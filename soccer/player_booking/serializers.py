from rest_framework import serializers

from dashboard_manage.models import Club
from management.models import Feature


class TagSerializer(serializers.Serializer):
    name = serializers.CharField()
    logo = serializers.ImageField()


class ClubListSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            "id",
            "name",
            "description",
            "address",
            "latitude",
            "longitude",
            "open_time",
            "close_time",
            "logo",
            "rating_avg",
            "rating_count",
            "flexible_reservation",
            "tags",
        ]

    def get_tags(self, obj):
        # Fast path: ActiveClubListAPIView prefetches to obj.active_features
        features = getattr(obj, "active_features", None)
        if features is None:
            # Fallback (still correct, but slower)
            features = (
                Feature.objects.select_related("tag")
                .filter(club=obj, is_active=True)
                .only("tag__name", "tag__logo")
            )
        return TagSerializer([f.tag for f in features], many=True, context=self.context).data


class ClubIDFilterSerializer(serializers.Serializer):
    club_id = serializers.UUIDField()
   
    # def validate(self, data):

    #     if data.get('from_time') and data.get('to_time'):
    #         if data['from_time'] >= data['to_time']:
    #             raise serializers.ValidationError("from_time must be before to_time")
    #     return data
