from django.db import IntegrityError, transaction
from dashboard_booking.models import  BookingNotification
from  player_booking.models import Booking, BookingStatus, BookingEquipment
from dashboard_manage.models import Pitch, ClubEquipment 
from rest_framework.exceptions import ValidationError 
from django.shortcuts import get_object_or_404
from core.models import User
from core.services.notification_service import NotificationService
from soccer.enm import BOOKING_STATUS_DENIED
from django.db.models import Prefetch, QuerySet
from django.db.models import Q
from player_competition.models import Challenge, ChallengePlayerBooking, ChallengeStatus
from player_team.models import MemberStatus, TeamMember
from .EquipmentBookingService import EquipmentBookingService
from django.db.models import F

class BookingService:
    
    
    @classmethod
    @transaction.atomic
    def owner_update_booking_status(cls, booking_id, status, club_id=None, user_id=None):
        user_notfication = False
        club_notfication = False
        if club_id is None and user_id is None:
            raise ValidationError({"error": "حدث خطأ"})
        
        elif club_id:
            booking = get_object_or_404(
                Booking.objects.select_for_update(), pk=booking_id, club_id=club_id
                )
            old_status = booking.get_status_display()
                    
            match status:
                case BookingStatus.PAY.value:
                    cls.convert_to_pay(booking)
                    title_player='تم قبول طلب الحجز من قبل النادي... يرجى الدفع'
                    title_club='تم قبول طلب حجز'
                    user_notfication = True
                case BookingStatus.REJECT.value:
                    cls.reject_booking(booking)
                    title_player='تم رفض طلب الحجز من قبل النادي'
                    title_club='تم رفض طلب حجز'
                    user_notfication = True
                case BookingStatus.DISPUTED.value:
                    cls.disputed_booking(booking)
                    title_player='تم تغيير حالة الحجز من قبل النادي'
                    title_club='تم تغيير حالة حجز'
                    user_notfication = True
                case BookingStatus.NO_SHOW.value:
                    cls.no_show_booking(booking)
                    title_player='تم تغيير حالة الحجز من قبل النادي'
                    title_club='تم تغيير حالة حجز'
                    user_notfication = True
                case BookingStatus.CANCELED.value:
                    cls.owner_canceled_booking(booking)
                    title_player='تم الغاء الحجز من قبل النادي'
                    title_club='تم الغاء حجز'
                    user_notfication = True
                case BookingStatus.COMPLETED.value:
                    cls.owner_completed_booking(booking)
                    title_player='تم تغيير حالة الحجز من قبل النادي'
                    title_club='تم تغيير حالة حجز'
                    user_notfication = True
                case _:
                    raise ValidationError({"error": "الحالة غير صحيحة"})
            
        elif user_id:   
            booking = get_object_or_404(
                Booking.objects.select_for_update(), pk=booking_id
                )
            old_status = booking.get_status_display()

            match status:
                case BookingStatus.CANCELED.value:
                    cls.player_canceled_booking(booking, user_id)  
                    title_player='تم الغاء حجز'
                    title_club='تم الغاء الحجز من قبل اللاعب'
                    club_notfication = True
                case _:
                    raise ValidationError({"error": "الحالة غير صحيحة"}) 

        if club_notfication:
            stuff=cls.get_club_workers(booking.club_id)
            
            print(booking.date)
            print(booking.start_time)
            print(booking.end_time)
            body = f"""
    إن الحجز في تاريخ: {booking.date}
    من الساعة {booking.start_time.strftime('%H:%M')} الى {booking.end_time.strftime('%H:%M')}
    تم تغيير حالته من {old_status} الى {booking.get_status_display()} 
    """

            for user in stuff:
                NotificationService.send_notification(
                    user=user,
                    title=title_club,
                    body=body,
                    notification_type='Booking_status',
                    helper_id=booking.id,
                )

        if user_notfication: 
            if booking.is_challenge:
                players = list(ChallengePlayerBooking.objects.only('player').filter(booking_id=booking.id).distinct())
                for cp in players:
                    NotificationService.send_notification(
                        user=cp.player,
                        title=title_player,
                        body=body,
                        notification_type='Booking_status',
                        helper_id=booking.id,
                    )
            elif booking.player is not None:
                NotificationService.send_notification(
                    user=booking.player,
                    title=title_player,
                    body=body,
                    notification_type='Booking_status',
                    helper_id=booking.id,
                )

    @classmethod
    @transaction.atomic
    def convert_to_pay(cls, booking):
        """Convert Pending_manager to pay"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise  ValidationError({"error": "فقط الحجوزات التي في حالة معلقة (من قبل المدير) يمكن تحويلها إلى معلقة بانتظار الدفع "})
        cls._check_if_has_overlap_booking(booking)

        print("//////////////////////////////////////////////////////////////////")
        print(booking.is_challenge)
        if booking.is_challenge:
            challenge = (
                Challenge.objects
                .filter(booking_id=booking.id)
                .only('id', 'team_id', 'challenged_team_id')
                .first()
            )
            print(challenge)
            print("//////////////////////////////////////////////////////////////////")

            if challenge:
                Challenge.objects.filter(id=challenge.id).update(status=ChallengeStatus.PAY)
                cls._seed_challenge_player_bookings(booking, challenge)
        else:
            if booking.player_id:
                User.objects.filter(id=booking.player_id).update(
                    booking_time=F('booking_time') + 1)

        booking.status = BookingStatus.PAY
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    @classmethod
    @transaction.atomic
    def reject_booking(cls, booking):
        """Reject booking (from Pending_manager)"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise ValidationError({"error": "فقط الحجوزات التي في حالة معلقة (من قبل المدير) يمكن إلغاؤها"})
        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.REJECTED)


        booking.status = BookingStatus.REJECT
        booking.save(update_fields=['status', 'updated_at'])
        return booking

    @classmethod
    @transaction.atomic
    def disputed_booking(cls, booking):
        """disputed booking (from Completed or Pending_pay)"""
        if not(
            booking.status == BookingStatus.COMPLETED or 
            (booking.status == BookingStatus.PENDING_PAY)):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع يمكن إلغاؤها"})
        
        booking.status = BookingStatus.DISPUTED
        booking.save(update_fields=['status', 'updated_at'])
        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.DISPUTED
                )
            players = ChallengePlayerBooking.objects.filter(booking_id=booking.id).values_list('player_id', flat=True)
            
            User.objects.filter(id__in=players).update(
            disputed_time=F('disputed_time') + 1)
        else:  
            if booking.player_id:
                User.objects.filter(id=booking.player_id).update(
                    disputed_time=F('disputed_time') + 1)
        
        return booking

    @classmethod
    @transaction.atomic
    def no_show_booking(cls, booking):
        """no_show booking (from Completed or Pending_pay)"""
        if not(booking.status == BookingStatus.PENDING_PAY):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع  يمكن إلغاؤها"})
        
        booking.status = BookingStatus.NO_SHOW
        booking.save(update_fields=['status', 'updated_at'])
        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.NO_SHOW)
            
            players = ChallengePlayerBooking.objects.filter(booking_id=booking.id).values_list('player_id', flat=True)
            
            User.objects.filter(id__in=players).update(
            no_show_time=F('no_show_time') + 1)
        else:    
            if booking.player_id:
                User.objects.filter(id=booking.player_id).update(
                    no_show_time=F('no_show_time') + 1)
            


        return booking
    
    @classmethod
    @transaction.atomic
    def owner_canceled_booking(cls, booking):
        """CANCELED booking (from Completed or Pending_pay) by owner"""
        if not(booking.status == BookingStatus.CLOSED or booking.status == BookingStatus.COMPLETED or booking.status == BookingStatus.PENDING_PAY):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع (تم انشاءها من قبل صاحب الملعب) او بانتظار اللاعب يمكن إلغاؤها"})
        
        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.CANCELED)

        booking.status = BookingStatus.CANCELED
        booking.save(update_fields=['status', 'updated_at'])
        
        
        return booking
    
    @classmethod
    @transaction.atomic
    def owner_completed_booking(cls, booking):
        """Completed booking (from Pending_pay) by owner"""
        if not(booking.by_owner and booking.status == BookingStatus.PENDING_PAY):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع (تم انشاءها من قبل صاحب الملعب) يمكن إلغاؤها"})

        booking.status = BookingStatus.COMPLETED
        booking.save(update_fields=['status', 'updated_at'])
        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.ACCEPTED)

        return booking
    
    @classmethod
    @transaction.atomic
    def convert_to_pending_player(cls, booking, club_id, new_date, new_start_time, new_end_time):
        """Convert Pending_manager to Pending_player and create notification"""
        if booking.status != BookingStatus.PENDING_MANAGER or booking.is_challenge:
            raise ValidationError({"error": "فقط الحجوزات التي في حالة معلقة (من قبل المدير) يمكن تحويلها إلى معلقة (من قبل اللاعب)"})
        
        if not booking.player:
            raise ValidationError({"error": "لا يمكن ارسال اشعار لهذا الحجز بسبب عدم وجود لاعب مرتبط به."})
        
        cls._check_if_has_overlap_booking(booking)
        
        # Create notification
        BookingNotification.objects.create(
            booking=booking,
            send_by_id=club_id,
            send_to=booking.player,
            old_date=booking.date,
            old_start_time=booking.start_time,
            old_end_time=booking.end_time,
            new_date=new_date,
            new_start_time=new_start_time,
            new_end_time=new_end_time
        )
        
        # Update booking status
        booking.status = BookingStatus.PENDING_PLAYER
        booking.save(update_fields=['status', 'updated_at'])
        return booking
  
    @classmethod
    def _check_if_has_overlap_booking(cls, booking:Booking):
        
        has_overlap = Booking.objects.select_for_update().filter(
            pitch=booking.pitch,
            date=booking.date,
            status__in=BOOKING_STATUS_DENIED,
            start_time__lt=booking.end_time,
            end_time__gt=booking.start_time
        ).exclude(pk=booking.pk).exists() 
        
        if has_overlap:
            raise ValidationError({"error": "لا يمكن تأكيد هذا الحجز بسبب وجود حجز آخر يتداخل مع نفس الملعب في نفس الوقت."})
        
        equipments = list(BookingEquipment.objects.values('equipment_id', 'quantity').filter(booking_id=booking.id))

        if equipments:
            equipment_ids = [ equipment['equipment_id'] for equipment in equipments]

            
            equipment_quantities = EquipmentBookingService.Get_booking_equipment_quantities(booking.club_id, booking.date, booking.start_time, booking.end_time, equipment_ids)

            old_booked_map = {
                item['equipment_id']: item['total_booked_quantity'] 
                for item in equipment_quantities
            }
            new_booked_map = {
                item['equipment_id']: item['quantity']
                for item in equipments
            }

            print("new_booked_map")
            print(new_booked_map)
            print("equipment_quantities")
            print(equipment_quantities)
            club_equipments = list(ClubEquipment.objects.select_for_update().values('id', 'quantity', 'price', 'equipment_id').filter(
                club_id=booking.club_id, is_active=True, id__in=equipment_ids, is_deteted=False
            ))
            print(club_equipments)
            print(":::::::::::::::::::::::::::::::::")
            print(equipment_ids)
            if len(club_equipments) != len(equipment_ids):  
                raise ValidationError({"error": "العدة يجب أن تكون نشطة."})

            for equipment in club_equipments:
                print(equipment['quantity'])
                print(old_booked_map.get(equipment['id'],0))
                print(new_booked_map.get(equipment['id'],0))
                quantity = (equipment['quantity'] - old_booked_map.get(equipment['id'],0)) - new_booked_map.get(equipment['id'],0)
                if quantity < 0:
                    raise ValidationError({
                                        "error": f"الكمية المطلوبة غير متوفرة.",
                                        "id": equipment["id"],
                                        })


    @classmethod
    def _seed_challenge_player_bookings(cls, booking, challenge):
        """Bulk-insert active players from both challenge teams into ChallengePlayerBooking."""
        active_members = list(
            TeamMember.objects
            .filter(
                team_id__in=[challenge.team_id, challenge.challenged_team_id],
                status=MemberStatus.ACTIVE,
            )
            .values_list('player_id', 'team_id')
        )

        player_ids = [player_id for player_id, _ in active_members]

        try:
            ChallengePlayerBooking.objects.bulk_create(
                [
                    ChallengePlayerBooking(
                        booking_id=booking.id,
                        challenge_id=challenge.id,
                        player_id=player_id,
                        team_id=team_id,
                    )
                    for player_id, team_id in active_members
                ],
            )
        except IntegrityError:
            raise ValidationError({
                "error": "لاعبون مسجلون مسبقاً في هذه المباراة"
            })

        
        User.objects.filter(id__in=player_ids).update(
            booking_time=F('booking_time') + 1,
            challenge_time=F('challenge_time') + 1,
        )
    
    @classmethod
    def get_club_workers(cls, club_id) -> QuerySet:
        return User.objects.filter(
            Q(club__id=club_id) |          # manager (related_name="club")
            Q(clubstaff__club_id=club_id)  # staff
        ).distinct()
    

    ################################## Player
    @classmethod
    @transaction.atomic
    def player_canceled_booking(cls, booking, user_id):
        """CANCELED booking (from Completed or Pending_pay) by player"""
        if not(booking.status in [
                                  BookingStatus.PENDING_MANAGER, 
                                  BookingStatus.PENDING_PAY, 
                                  BookingStatus.COMPLETED, 
                                  BookingStatus.PAY,
                                  
                                  ]):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع (من قبل اللاعب) يمكن إلغاؤها"})

        if booking.is_challenge:
            players = list(ChallengePlayerBooking.objects.filter(booking_id=booking.id).values_list('player_id', flat=True))
            if not(user_id in players):
                raise ValidationError({"error": "لست جزء من التحدي"})

            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.CANCELED)
            if not booking.status in [BookingStatus.COMPLETED, BookingStatus.PENDING_MANAGER]:
                User.objects.filter(id__in=players).update(
                cancel_time=F('cancel_time') + 1)
        
        else:
            if not booking.status in [BookingStatus.COMPLETED, BookingStatus.PENDING_MANAGER]:

                if booking.player_id is not None and booking.player_id==user_id:
                    User.objects.filter(id=user_id).update(
                        cancel_time=F('cancel_time') + 1)
                else:
                    raise ValidationError({"error": "لا يمكنك الغاء الحجز"})
        
                

        booking.status = BookingStatus.CANCELED
        booking.save(update_fields=['status', 'updated_at'])
        return booking
