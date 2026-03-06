from dashboard_manage.models import Club, ClubPricing
from player_booking.models import Booking
from soccer.enm import BOOKING_STATUS_DENIED
from django.db.models import Q

class ClubInfoService:
    @classmethod
    def get_free_booking_time(cls, pitch_id, club_id, date):
        """Process the validated data"""


        bookings = Booking.objects.only('start_time', 'end_time').filter(
            pitch_id=pitch_id,
            club_id=club_id,
            date=date,
            status__in=BOOKING_STATUS_DENIED
        ).order_by('start_time')
        
        # consolidated_slots = self._consolidate_time_slots(bookings)
        
        # return Response(consolidated_slots)
        open_time, close_time=cls.get_open_close_time_club(club_id, date)
        free_slots = cls.get_free_slots(bookings, day_start=open_time, day_end=close_time)

        return free_slots
    
    @classmethod
    def get_free_slots(cls, bookings, day_start, day_end):
        """Return free (unbooked) time slots within the day"""
        if not bookings.exists():
            # Whole day is free
            return [{'from': day_start.strftime('%H:%M'), 'to': day_end.strftime('%H:%M')}]

        # Step 1: consolidate booked slots (same logic as before)
        time_slots = [(b.start_time, b.end_time) for b in bookings]
        time_slots.sort(key=lambda x: x[0])

        booked = []
        current_start, current_end = time_slots[0]
        for start, end in time_slots[1:]:
            if start <= current_end:
                current_end = max(current_end, end)
            else:
                booked.append((current_start, current_end))
                current_start, current_end = start, end
        booked.append((current_start, current_end))

        # Step 2: invert booked slots to get free slots
        free = []
        cursor = day_start

        for booked_start, booked_end in booked:
            if cursor < booked_start:
                free.append({
                    'from': cursor.strftime('%H:%M'),
                    'to': booked_start.strftime('%H:%M')
                })
            cursor = max(cursor, booked_end)

        # Free time after last booking
        if cursor < day_end:
            free.append({
                'from': cursor.strftime('%H:%M'),
                'to': day_end.strftime('%H:%M')
            })

        return free
    

    @classmethod
    def get_open_close_time_club(cls, club_id, date):
        
        weekday=(date.weekday() + 2) % 7

        time=ClubPricing.objects.values('end_time', 'start_time').filter(club_id=club_id).filter(Q(date=date) | Q(day_of_week=weekday)).order_by('-type')
        print(time)

        if time:
            print(time[0]['start_time'], time[0]['end_time'])
            return time[0]['start_time'], time[0]['end_time']
        
        time=Club.objects.values('close_time', 'open_time').filter(id=club_id).first()
        return time['open_time'], time['close_time']



