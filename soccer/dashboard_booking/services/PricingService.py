from decimal import Decimal, ROUND_HALF_UP
from dashboard_manage.models import ClubPricing, Pitch
from django.db.models import Q

class PricingService:
    
    @classmethod
    def calculate_final_price(cls, pitch:Pitch, club_id, date, start_time, end_time):
        time_interval, price_first, price_second = cls.get_price_rule(pitch, club_id, date)
        
        total_price = cls.calculate_price(start_time, end_time, time_interval, price_first, price_second)
        return total_price.quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
    

    @classmethod
    def to_seconds(cls, t):
        """Helper to convert a time object to integer seconds."""
        return (t.hour * 3600) + (t.minute * 60) + t.second

    @classmethod
    def calculate_price(cls, start_time, end_time, pricing_rule_time, price_befor_the_time, price_after_the_time):
        # 1. Convert everything to integers (Fastest for CPU)
        start_sec = cls.to_seconds(start_time)
        end_sec = cls.to_seconds(end_time)
        cutoff_sec = cls.to_seconds(pricing_rule_time)
        
        if end_sec <= start_sec:
            end_sec += 86400 # Add 24 hours in seconds
        
        # 2. Calculate "Before" Seconds (Clamping)
        # Logic: The 'before' segment ends at either the reservation end OR the cutoff (whichever comes first).
        # We subtract the start time from that. 
        # max(0, ...) ensures we don't get negative numbers if the whole reservation is after the cutoff.
        seconds_before = max(0, min(end_sec, cutoff_sec) - start_sec)

        # 3. Calculate "After" Seconds (Clamping)
        # Logic: The 'after' segment starts at either the reservation start OR the cutoff (whichever comes last).
        # We subtract that starting point from the end time.
        seconds_after = max(0, end_sec - max(start_sec, cutoff_sec))

        hours_before = Decimal(seconds_before) / Decimal(3600)
        hours_after = Decimal(seconds_after) / Decimal(3600)

        total_price = (hours_before * price_befor_the_time) + \
                    (hours_after * price_after_the_time)
        return total_price
    
    @classmethod
    def get_percent(cls, club_id, date):
        weekday_num = date.weekday()

        rules = ClubPricing.objects.filter(club_id=club_id).filter(
            Q(type=2, date=date) |  
            Q(type=1, day_of_week=weekday_num)  
        ).values('type', 'percent')

        date_rule = next((r for r in rules if r['type'] == 2), None)
        if date_rule:
            return  date_rule['percent']

        weekday_rule = next((r for r in rules if r['type'] == 1), None)
        if weekday_rule:
            return weekday_rule['percent']
        return Decimal("1")

    @classmethod
    def get_price_rule(cls, pitch:Pitch, club_id, date):
        
        time_interval=pitch.time_interval
        price_first=pitch.price_first
        price_second=pitch.price_second

        percent=cls.get_percent(club_id, date)

        return time_interval, price_first*percent, price_second*percent
    


