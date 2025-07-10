from flask import Blueprint, render_template, request, redirect, session, url_for
from .calendar_api import get_flow, get_calendar_service, create_calendar_event
from .planner import extract_task_details, find_free_slot
from .deepseek_parser import call_deepseek  # ✅ DeepSeek fallback parser
import pickle
import datetime

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    message = None
    upcoming_events = []

    if "credentials" not in session:
        return redirect(url_for("main.login"))

    creds = pickle.loads(bytes.fromhex(session["credentials"]))
    service = get_calendar_service(creds)

    if request.method == 'POST':
        task = request.form['task']

        # Try local parser first
        title, start_time, duration = extract_task_details(task)

        # If local parser fails, use DeepSeek
        if not all([title, duration]):
            title, start_time, duration = call_deepseek(task)

        if title and duration:
            try:
                # If no start_time, find a free one
                if not start_time:
                    start_time = find_free_slot(service, datetime.datetime.now().date(), int(duration.total_seconds() / 60))
                    if not start_time:
                        raise Exception("No available time slots found for today.")

                end_time = start_time + duration

                # Check for duplicate events
                events = service.events().list(
                    calendarId='primary',
                    timeMin=datetime.datetime.utcnow().isoformat() + 'Z',
                    timeMax=(datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat() + 'Z',
                    q=title,
                    singleEvents=True
                ).execute().get('items', [])

                if events:
                    message = f"🟡 You already have an event titled '{title}' this week. Consider updating it."
                else:
                    create_calendar_event(service, title, start_time, end_time)
                    message = f"✅ Scheduled '{title}' on {start_time.strftime('%A, %B %d')} at {start_time.strftime('%I:%M %p')}"

            except Exception as e:
                message = f"❌ {str(e)}"
        else:
            message = "⚠️ Couldn't understand your task. Try phrasing it like 'Study AI for 2 hours tomorrow at 5pm'."

    # Display upcoming events
    try:
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        upcoming_events = events_result.get('items', [])
    except Exception as e:
        message = f"⚠️ Couldn't fetch events: {str(e)}"

    return render_template('index.html', message=message, upcoming=upcoming_events)


@main.route('/login')
def login():
    flow = get_flow()
    auth_url, _ = flow.authorization_url(prompt='consent')
    return redirect(auth_url)


@main.route('/oauth2callback')
def oauth2callback():
    flow = get_flow()
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session["credentials"] = pickle.dumps(creds).hex()
    return redirect(url_for('main.index'))


@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))
