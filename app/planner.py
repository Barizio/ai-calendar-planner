import dateparser
import datetime
import re

def extract_task_details(task_str):
    match = re.search(r'(.+?) for (\d+)\s*(minutes|minute|hours|hour)\s*(.*)', task_str, re.IGNORECASE)
    if not match:
        return None, None, None

    title = match.group(1).strip()
    duration_val = int(match.group(2))
    unit = match.group(3).lower()
    time_expression = match.group(4).strip()

    duration = datetime.timedelta(hours=duration_val) if "hour" in unit else datetime.timedelta(minutes=duration_val)
    start_time = dateparser.parse(time_expression) if time_expression else None

    return title, start_time, duration

def find_free_slot(service, date, duration_mins=60):
    start = datetime.datetime.combine(date, datetime.time(8, 0))
    end = datetime.datetime.combine(date, datetime.time(20, 0))
    events = service.events().list(
        calendarId='primary',
        timeMin=start.isoformat() + 'Z',
        timeMax=end.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])

    current_time = start
    for event in events:
        event_start = dateparser.parse(event['start'].get('dateTime', event['start'].get('date')))
        if (event_start - current_time).total_seconds() >= duration_mins * 60:
            return current_time
        event_end = dateparser.parse(event['end'].get('dateTime', event['end'].get('date')))
        current_time = max(current_time, event_end)

    if (end - current_time).total_seconds() >= duration_mins * 60:
        return current_time

    return None
