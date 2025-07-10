import dateparser
import datetime
import re
from typing import Tuple, Optional

def extract_task_details(task_str: str) -> Tuple[Optional[str], Optional[datetime.datetime], Optional[datetime.timedelta]]:
    """
    Enhanced task extraction with multiple pattern matching approaches
    Handles various natural language formats like:
    - "KPMG meeting tomorrow by 5pm for 3 hours"
    - "Study AI for 2 hours tomorrow at 4pm"
    - "Team meeting next Monday 10am for 1 hour"
    - "Doctor appointment Friday at 2pm"
    """
    task_str = task_str.strip()
    
    # Pattern 1: [task] [time] for [duration]
    pattern1 = r'(.+?)\s+(?:at|by|@)\s+(.+?)\s+for\s+(\d+)\s*(hours?|hrs?|minutes?|mins?)'
    match1 = re.search(pattern1, task_str, re.IGNORECASE)
    
    if match1:
        title = match1.group(1).strip()
        time_expr = match1.group(2).strip()
        duration_val = int(match1.group(3))
        unit = match1.group(4).lower()
        
        duration = datetime.timedelta(hours=duration_val) if 'hour' in unit or 'hr' in unit else datetime.timedelta(minutes=duration_val)
        start_time = dateparser.parse(time_expr, settings={'PREFER_DATES_FROM': 'future'})
        
        return title, start_time, duration
    
    # Pattern 2: [task] for [duration] [time]
    pattern2 = r'(.+?)\s+for\s+(\d+)\s*(hours?|hrs?|minutes?|mins?)\s+(.+)'
    match2 = re.search(pattern2, task_str, re.IGNORECASE)
    
    if match2:
        title = match2.group(1).strip()
        duration_val = int(match2.group(2))
        unit = match2.group(3).lower()
        time_expr = match2.group(4).strip()
        
        duration = datetime.timedelta(hours=duration_val) if 'hour' in unit or 'hr' in unit else datetime.timedelta(minutes=duration_val)
        start_time = dateparser.parse(time_expr, settings={'PREFER_DATES_FROM': 'future'})
        
        return title, start_time, duration
    
    # Pattern 3: [task] [time] (no explicit duration - default to 1 hour)
    pattern3 = r'(.+?)\s+(?:at|by|@|on)\s+(.+)'
    match3 = re.search(pattern3, task_str, re.IGNORECASE)
    
    if match3:
        title = match3.group(1).strip()
        time_expr = match3.group(2).strip()
        
        start_time = dateparser.parse(time_expr, settings={'PREFER_DATES_FROM': 'future'})
        duration = datetime.timedelta(hours=1)  # Default duration
        
        return title, start_time, duration
    
    # Pattern 4: Just task name (no time, no duration)
    if task_str:
        return task_str, None, datetime.timedelta(hours=1)
    
    return None, None, None

def find_free_slot(service, date: datetime.date, duration_mins: int = 60) -> Optional[datetime.datetime]:
    """
    Find the next available time slot for a given duration
    """
    try:
        # Set working hours (8 AM to 8 PM)
        start = datetime.datetime.combine(date, datetime.time(8, 0))
        end = datetime.datetime.combine(date, datetime.time(20, 0))
        
        # Make timezone-aware
        start = start.replace(tzinfo=datetime.timezone.utc)
        end = end.replace(tzinfo=datetime.timezone.utc)
        
        # Get existing events for the day
        events = service.events().list(
            calendarId='primary',
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute().get('items', [])
        
        current_time = start
        
        for event in events:
            event_start_str = event['start'].get('dateTime', event['start'].get('date'))
            event_end_str = event['end'].get('dateTime', event['end'].get('date'))
            
            event_start = dateparser.parse(event_start_str)
            event_end = dateparser.parse(event_end_str)
            
            # Check if there's enough time before this event
            if event_start and (event_start - current_time).total_seconds() >= duration_mins * 60:
                return current_time.replace(tzinfo=None)  # Remove timezone for consistency
            
            # Move current time to after this event
            if event_end:
                current_time = max(current_time, event_end)
        
        # Check if there's time after all events
        if (end - current_time).total_seconds() >= duration_mins * 60:
            return current_time.replace(tzinfo=None)
        
    except Exception as e:
        print(f"Error finding free slot: {e}")
        # Fallback: suggest next hour
        now = datetime.datetime.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
        return next_hour
    
    return None

def validate_task_input(task_str: str) -> Tuple[bool, str]:
    """
    Validate user input and provide helpful feedback
    """
    if not task_str or not task_str.strip():
        return False, "Please enter a task description"
    
    if len(task_str) > 200:
        return False, "Task description is too long (max 200 characters)"
    
    # Check for common issues
    if not re.search(r'[a-zA-Z]', task_str):
        return False, "Task should contain at least some text"
    
    return True, ""

def suggest_clarification(task_str: str, parsed_title: str = None, parsed_time: datetime.datetime = None, parsed_duration: datetime.timedelta = None) -> str:
    """
    Generate clarification questions based on what's missing
    """
    missing = []
    
    if not parsed_title:
        missing.append("task description")
    
    if not parsed_time:
        missing.append("time")
    
    if not parsed_duration:
        missing.append("duration")
    
    if missing:
        if len(missing) == 1:
            return f"Could you specify the {missing[0]}? For example: 'Meeting with John tomorrow at 2pm for 1 hour'"
        else:
            return f"Could you specify the {' and '.join(missing)}? For example: 'KPMG meeting tomorrow by 5pm for 3 hours'"
    
    return ""