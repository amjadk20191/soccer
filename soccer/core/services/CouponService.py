from django.core.exceptions import ValidationError
from django.db import transaction
from player_booking.models import Coupon, CouponUsage
from django.db.models import F

from rest_framework import serializers

class CouponService:

    @staticmethod
    def apply_coupon(price, coupon_code, user=None, club_id=None):
        try:
            coupon = Coupon.objects.get(code=coupon_code)
        except Coupon.DoesNotExist:
            raise serializers.ValidationError({'error': 'كود الكوبون غير موجود.'})

        if not coupon.is_valid():
            raise serializers.ValidationError({'error': 'الكوبون غير صالح أو منتهي الصلاحية.'})
        print("DEBUG coupon.club_id:", repr(coupon.club_id), type(coupon.club_id))
        print("DEBUG club_id param:", repr(club_id), type(club_id))
        print("DEBUG str comparison:", str(coupon.club_id), "==", str(club_id))
        # Check if coupon is restricted to a specific club
        if coupon.club is not None:
            if club_id is None:
                raise serializers.ValidationError({'error': 'هذا الكوبون مخصص لنادي معين فقط.'})
            if str(coupon.club_id) != str(club_id):
                raise serializers.ValidationError({'error': 'هذا الكوبون غير صالح لهذا النادي.'})

        # Check if this specific user already used the coupon
        if user is not None:
            already_used = CouponUsage.objects.filter(coupon=coupon, user=user).exists()
            if already_used:
                raise serializers.ValidationError({'error': 'لقد استخدمت هذا الكوبون من قبل.'})

        discounted_price = coupon.apply_discount(price)

        return {
            'coupon': coupon,
            'discount': price - discounted_price,
            'coupon_applied': True,
            'price': discounted_price
        }

    @staticmethod
    def redeem_coupon(coupon, user=None):
        """
        Call this AFTER booking is confirmed to record usage.
        Separated from apply_coupon so you can validate first, redeem after save.
        """
        print("DEBUG inside redeem_coupon, coupon:", repr(coupon), "user:", repr(user))
        # Increment used_count atomically to prevent race conditions
        Coupon.objects.filter(pk=coupon.pk).update(used_count=F('used_count') + 1)
        print("DEBUG used_count updated")
        if user is not None:
            CouponUsage.objects.create(coupon=coupon, user=user)
            print("DEBUG CouponUsage created")