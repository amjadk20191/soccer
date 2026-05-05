from player_booking.models import BookingStatus





BOOKING_STATUS_DENIED = [
            BookingStatus.PENDING_PAY.value,
            BookingStatus.PAY.value,
            BookingStatus.CHECK_PAY.value,
            BookingStatus.COMPLETED.value,
            BookingStatus.PENDING_PLAYER.value,
            BookingStatus.CLOSED.value,
            BookingStatus.DISPUTED.value,
        ]