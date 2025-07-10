import os
import pickle
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
CLIENT_SECRETS_FILE = "credentials.json"

# Automatically switch between local and production
def get_flow():
    redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:5000/oauth2callback")
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

def get_calendar_service(creds=None):
    if not creds:
        return None
    return build('calendar', 'v3', credentials=creds)

def create_calendar_event(service, title, start_time, end_time):
    event = {
        'summary': title,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Africa/Lagos'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Africa/Lagos'},
    }
    return service.events().insert(calendarId='primary', body=event).execute()
