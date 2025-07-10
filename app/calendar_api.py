import os
import pickle
import datetime
from typing import Optional, Dict, Any, List
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import dateparser

SCOPES = ['https://www.googleapis.com/auth/calendar']
CLIENT_SECRETS_FILE = "credentials.json"

def get_flow():
    """Create OAuth flow with automatic environment detection"""
    redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:5000/oauth2callback")
    
    try:
        return Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
    except FileNotFoundError:
        raise Exception("credentials.json file not found. Please ensure it's in the project root.")
    except Exception as e:
        raise Exception(f"Error creating OAuth flow: {str(e)}")

def get_calendar_service(creds=None):
    """Get authenticated calendar service"""
    if not creds:
        return None
    
    try:
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error creating calendar service: {e}")
        return None

def create_calendar_event(service, title: str, start_time: datetime.datetime, end_time: datetime.datetime, description: str = "") -> Dict[str, Any]:
    """
    Create a calendar event with enhanced error handling and validation
    """
    try:
        # Validate inputs
        if not title or not title.strip():
            raise ValueError("Event title is required")
        
        if not start_time or not end_time:
            raise ValueError("Start and end times are required")
        
        if start_time >= end_time:
            raise ValueError("Start time must be before end time")
        
        # Format times properly
        event_body = {
            'summary': title.strip(),
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Africa/Lagos'
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Africa/Lagos'
            },
            'description': description,
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 10},
                    {'method': 'email', 'minutes': 60}
                ]
            }
        }
        
        # Create the event
        event = service.events().insert(
            calendarId='primary',
            body=event_body,
            sendNotifications=True
        ).execute()
        
        return {
            'success': True,
            'event': event,
            'message': f"Successfully created event: {title}"
        }
        
    except HttpError as e:
        error_msg = f"Google Calendar API error: {e.resp.status} - {e.content.decode()}"
        return {
            'success': False,
            'error': error_msg,
            'message': "Failed to create calendar event due to API error"
        }
    except ValueError as e:
        return {
            'success': False,
            'error': str(e),
            'message': f"Invalid event data: {str(e)}"
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f"Unexpected error: {str(e)}"
        }

def check_event_conflicts(service, start_time: datetime.datetime, end_time: datetime.datetime) -> Dict[str, Any]:
    """
    Check for conflicting events in the specified time range
    """
    try:
        # Query for events in the time range
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_time.isoformat() + 'Z',
            timeMax=end_time.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if events:
            conflict_details = []
            for event in events:
                event_start = event['start'].get('dateTime', event['start'].get('date'))
                event_end = event['end'].get('dateTime', event['end'].get('date'))
                
                conflict_details.append({
                    'title': event.get('summary', 'Untitled Event'),
                    'start': event_start,
                    'end': event_end
                })
            
            return {
                'has_conflicts': True,
                'conflicts': conflict_details,
                'message': f"Found {len(events)} conflicting event(s)"
            }
        
        return {
            'has_conflicts': False,
            'conflicts': [],
            'message': "No conflicts found"
        }
        
    except Exception as e:
        return {
            'has_conflicts': False,
            'conflicts': [],
            'message': f"Error checking conflicts: {str(e)}"
        }

def get_upcoming_events(service, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Get upcoming events with better formatting
    """
    try:
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        formatted_events = []
        
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Parse and format the datetime
            start_dt = dateparser.parse(start)
            end_dt = dateparser.parse(end)
            
            formatted_event = {
                'id': event.get('id'),
                'title': event.get('summary', 'Untitled Event'),
                'start': start,
                'end': end,
                'start_formatted': start_dt.strftime('%A, %B %d at %I:%M %p') if start_dt else start,
                'duration': str(end_dt - start_dt).split('.')[0] if start_dt and end_dt else 'Unknown',
                'description': event.get('description', ''),
                'location': event.get('location', '')
            }
            
            formatted_events.append(formatted_event)
        
        return formatted_events
        
    except Exception as e:
        print(f"Error fetching upcoming events: {e}")
        return []

def search_events(service, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Search for events by title/description
    """
    try:
        events_result = service.events().list(
            calendarId='primary',
            q=query,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
        
    except Exception as e:
        print(f"Error searching events: {e}")
        return []