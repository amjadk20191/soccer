from decimal import Decimal, ROUND_HALF_UP
from dashboard_manage.models import ClubPricing, Pitch, Club
from django.db.models import Q
from datetime import date, timedelta
from rest_framework.exceptions import ValidationError
from django.core.files.storage import default_storage
class ClubTimeForOwnerService:
    """
    Service class for managing club time schedules and pricing calculations.
    
    This service handles:
    - Fetching club opening/closing times
    - Applying pricing rules (default, weekly exceptions, specific date exceptions)
    - Calculating adjusted pitch prices based on time-based pricing multipliers
    """
   
    @classmethod
    def get_opening_time_with_pitches_prices(cls, club_id, number_of_day, request):
        """
        Main method: Returns opening times and pitch prices for a date range.
        
        For each day in the range, calculates:
        - Opening/closing times (may vary by day based on exceptions)
        - Adjusted pitch prices (base price * pricing multiplier for that day)
        
        Args:
            club_id: ID of the club
            number_of_day: Number of days from today to include in the range
            
        Returns:
            List of dictionaries, each containing:
            - date: Date string
            - start_time: Opening time for that day
            - end_time: Closing time for that day
            - pitches: List of pitch dictionaries with adjusted prices
        """
        # Fetch all pitches for this club (ordered by type, then name)
        pitches = Pitch.objects.filter(club_id=club_id).values('id', 'name', 'price_first',
                                                                'price_second', 'time_interval', 'type',
                                                                'size_high', 'size_width', 'image','is_active'
                                                                ).order_by('type', 'name')  
        
        # Get daily configurations: for each date, get the pricing multiplier (percent) 
        # and opening/closing times based on club defaults and any exceptions
        time_percents = cls.get_opening_time_with_percent(club_id, number_of_day)

        # Pre-define quantizer for price rounding (round to 2 decimal places)
        quantizer = Decimal("1.00")

        # Build the result list: one entry per day
        opening_with_prices = []
        
        # Process each day in the date range
        for date_key, day_config in time_percents.items():
            # Cache the pricing multiplier to avoid repeated dict lookups
            # This percent (e.g., 1.0, 1.5, 0.8) will be applied to base pitch prices
            current_percent = day_config['percent']
            
            # Create the day structure with date and time information
            day_opening_with_prices = {
                'date': date_key,
                'start_time': day_config['start_time'],
                'end_time': day_config['end_time'],
                'pitches': []
            }
            
            # Process each pitch: apply the day's pricing multiplier to base prices
            for pitch in pitches:
                # Build pitch entry with adjusted prices
                # price_first and price_second are multiplied by the day's percent,
                # then rounded to 2 decimal places
                pitch_entry = {
                    'id': pitch['id'],
                    'name': pitch['name'],
                    # Apply pricing multiplier and round to 2 decimals
                    'price_first': (pitch['price_first'] * current_percent).quantize(quantizer, rounding=ROUND_HALF_UP),
                    'price_second': (pitch['price_second'] * current_percent).quantize(quantizer, rounding=ROUND_HALF_UP),
                    'time_interval': pitch['time_interval'],
                    'type': pitch['type'],
                    'size_high': pitch['size_high'],
                    'size_width': pitch['size_width'],
                    'image': request.build_absolute_uri(default_storage.url(pitch['image'])) ,
                    'is_active': pitch['is_active']
                }
                
                day_opening_with_prices['pitches'].append(pitch_entry)

            opening_with_prices.append(day_opening_with_prices)
        return opening_with_prices
 
    @classmethod
    def get_club_general_time(cls, club_id):
        """
        Fetches the default opening and closing times for a club.
        
        These are the standard hours that apply when no exceptions are configured.
        
        Args:
            club_id: ID of the club
            
        Returns:
            Tuple of (open_time, close_time)
            
        Raises:
            ValidationError: If club is not found
        """
        club = Club.objects.values('open_time', 'close_time', 'working_days').filter(id=club_id).first()
        if not club:
            raise ValidationError({"detail": "Club not found"})

        return club['open_time'], club['close_time'], club['working_days']

    @classmethod
    def get_exception_day(cls, club_id, number_of_day):
        """
        Fetches pricing exceptions (special rules) for the date range.
        
        Two types of exceptions:
        - type=1: Weekly recurring exceptions (e.g., "Every Monday has 20% discount")
        - type=2: Specific date exceptions (e.g., "Christmas Day has special hours")
        
        Also generates the date range and maps dates to weekday indices.
        
        Note: The weekday mapping uses (weekday() + 2) % 7 to convert Python's 
        weekday (0=Monday) to the custom system (0=Wednesday, based on the formula).
        
        Args:
            club_id: ID of the club
            number_of_day: Number of days from today to include
            
        Returns:
            Tuple of:
            - exception_days: QuerySet of ClubPricing exceptions
            - dates: List of date objects in the range
            - day_indices: List of weekday indices corresponding to dates
        """
        # Generate date range: today, today+1, today+2, ..., today+(number_of_day-1)
        today = date.today()
        dates = [today + timedelta(days=i) for i in range(number_of_day)]
        
        # Convert Python weekday (0=Monday, 6=Sunday) to custom weekday index
        # Formula: (weekday + 2) % 7 maps Monday(0)->2, Tuesday(1)->3, ..., Sunday(6)->1
        day_indices = [(d.weekday() + 2) % 7 for d in dates]

        # Fetch exceptions that apply to this date range:
        # - type=2: Specific dates that match any date in our range
        # - type=1: Weekly recurring rules that match any weekday in our range
        exception_days = ClubPricing.objects.filter(club_id=club_id).filter(
            Q(type=2, date__in=dates) |  # Specific date exceptions
            Q(type=1, day_of_week__in=day_indices)  # Weekly recurring exceptions
        ).values('date', 'day_of_week', 'percent', 'start_time', 'end_time', 'type').order_by('-type')
        
        return exception_days, dates, day_indices

    @classmethod
    def get_opening_time_with_percent(cls, club_id, number_of_day):
        """
        Determines the pricing multiplier and opening hours for each day in the range.
        
        This method applies a priority system to determine which rules apply:
        1. Specific Date exceptions (type=2) - Highest priority
           Example: "December 25th has 50% discount and special hours"
        2. Weekly Recurring exceptions (type=1) - Medium priority
           Example: "Every Monday has 20% discount"
        3. Default club settings - Lowest priority (fallback)
           Uses club's standard open_time, close_time, and 100% pricing (1.00)
        
        Args:
            club_id: ID of the club
            number_of_day: Number of days from today to include
            
        Returns:
            Dictionary mapping date strings to configuration dicts:
            {
                '2024-01-15': {
                    'percent': Decimal('1.20'),  # 20% price increase
                    'start_time': time(9, 0),   # Opening time
                    'end_time': time(22, 0),    # Closing time
                    'weekday': 2                # Custom weekday index
                },
                ...
            }
        """
        # Get default club hours (used when no exceptions apply)
        open_time, close_time, working_days = cls.get_club_general_time(club_id)
        
        # Get all exceptions and date range information
        exception_days, dates, day_indices = cls.get_exception_day(club_id, number_of_day)
        
        # Build lookup dictionaries for O(1) access instead of linear search
        # This optimization allows fast rule lookup by date or weekday
        # Priority: Specific Date (type 2) > Weekly Recurring (type 1) > Default
        specific_date_rules = {}  # type 2: date object -> rule dict
        weekly_rules = {}  # type 1: weekday index -> rule dict
        
        # Organize exceptions into lookup dictionaries
        for day in exception_days:
            if day['type'] == 2:  # Specific Date exception
                # Map the date directly to its rule
                specific_date_rules[day['date']] = day
            elif day['type'] == 1:  # Weekly Recurring exception
                # Map weekday index to its rule
                # Note: If multiple rules exist for same weekday, last one wins
                # (due to order_by('-type') in query)
                weekly_rules[day['day_of_week']] = day
        
        # Build time_percents dict by processing each date once
        # This is more efficient than the original nested loop approach
        time_percents = {}
        for i, current_date in enumerate(dates):
            date_key = str(current_date)  # Convert to string for dict key
            weekday_idx = day_indices[i]  # Get corresponding weekday index
            
            # Determine which rule applies using priority system
            rule = None
            # Priority 1: Check for specific date exception (highest priority)
            if current_date in specific_date_rules:
                rule = specific_date_rules[current_date]
            # Priority 2: Check for weekly recurring exception (if no specific date rule)
            elif weekday_idx in weekly_rules:
                rule = weekly_rules[weekday_idx]
            # Priority 3: Use defaults (if no exceptions found)
            
            # Apply the rule or use defaults
            if rule:
                # Use exception rule: custom percent, start_time, end_time
                time_percents[date_key] = {
                    'percent': rule['percent'],  # Pricing multiplier (e.g., 1.2 for 20% increase)
                    'start_time': rule['start_time'],  # Custom opening time
                    'end_time': rule['end_time'],  # Custom closing time
                    'weekday': weekday_idx
                }
            elif working_days[str(weekday_idx)]:
                # Use default club settings: 100% pricing, standard hours
                time_percents[date_key] = {
                    'percent': Decimal('1.00'),  # No price adjustment
                    'start_time': open_time,  # Standard opening time
                    'end_time': close_time,  # Standard closing time
                    'weekday': weekday_idx
                }
            

        return time_percents




             
                                                                