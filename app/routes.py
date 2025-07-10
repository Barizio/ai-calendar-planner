from flask import Blueprint, render_template, request, redirect, session, url_for, jsonify
from .calendar_api import get_flow, get_calendar_service, create_calendar_event
from .planner import find_free_slot
from .deepseek_parser import call_deepseek, parse_natural_language
import pickle
import datetime
import json

main = Blueprint('main', __name__)

def get_conversation_history():
    """Get conversation history from session"""
    return session.get('conversation_history', [])

def add_to_conversation(user_input, assistant_response):
    """Add exchange to conversation history"""
    if 'conversation_history' not in session:
        session['conversation_history'] = []
    
    session['conversation_history'].append({
        'user': user_input,
        'assistant': assistant_response,
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    # Keep only last 10 exchanges
    if len(session['conversation_history']) > 10:
        session['conversation_history'] = session['conversation_history'][-10:]
    
    session.modified = True

@main.route('/', methods=['GET', 'POST'])
def index():
    message = None
    upcoming_events = []
    conversation_history = get_conversation_history()
    needs_clarification = False
    clarification_question = None

    if "credentials" not in session:
        return redirect(url_for("main.login"))

    try:
        creds = pickle.loads(bytes.fromhex(session["credentials"]))
        service = get_calendar_service(creds)
    except Exception as e:
        session.clear()
        return redirect(url_for("main.login"))

    if request.method == 'POST':
        task = request.form.get('task', '').strip()
        if not task:
            message = "⚠️ Please enter a task description."
            return render_template('index.html', message=message, upcoming=upcoming_events, 
                                 conversation=conversation_history, needs_clarification=needs_clarification)

        try:
            # Try local parser first for simple cases
            title, start_time, duration = parse_natural_language(task)
            clarification_question = None
            
            # If local parser fails, use AI parser
            if not all([title, start_time, duration]):
                title, start_time, duration, clarification_question = call_deepseek(task, conversation_history)
            
            # Handle clarification needed
            if clarification_question:
                needs_clarification = True
                message = f"🤔 {clarification_question}"
                add_to_conversation(task, clarification_question)
                return render_template('index.html', message=message, upcoming=upcoming_events,
                                     conversation=conversation_history, needs_clarification=needs_clarification,
                                     clarification_question=clarification_question)
            
            # Validate parsed data
            if not title or not duration:
                message = "⚠️ I couldn't understand your task. Please try: 'KPMG meeting tomorrow 5pm for 3 hours'"
                add_to_conversation(task, message)
                return render_template('index.html', message=message, upcoming=upcoming_events,
                                     conversation=conversation_history)
            
            # Handle missing start time - find free slot
            if not start_time:
                today = datetime.datetime.now().date()
                duration_minutes = int(duration.total_seconds() / 60)
                start_time = find_free_slot(service, today, duration_minutes)
                
                if not start_time:
                    # Try next day
                    tomorrow = today + datetime.timedelta(days=1)
                    start_time = find_free_slot(service, tomorrow, duration_minutes)
                
                if not start_time:
                    message = "⚠️ No available time slots found. Please specify a time."
                    add_to_conversation(task, message)
                    return render_template('index.html', message=message, upcoming=upcoming_events,
                                         conversation=conversation_history)
            
            # Validate start time is in future
            if start_time < datetime.datetime.now():
                message = "⚠️ Cannot schedule tasks in the past. Please choose a future time."
                add_to_conversation(task, message)
                return render_template('index.html', message=message, upcoming=upcoming_events,
                                     conversation=conversation_history)
            
            end_time = start_time + duration
            
            # Check for conflicts
            events = service.events().list(
                calendarId='primary',
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True
            ).execute().get('items', [])
            
            if events:
                conflict_titles = [event.get('summary', 'Untitled') for event in events]
                message = f"⚠️ Time conflict with: {', '.join(conflict_titles)}. Please choose a different time."
                add_to_conversation(task, message)
                return render_template('index.html', message=message, upcoming=upcoming_events,
                                     conversation=conversation_history)
            
            # Check for duplicates
            duplicate_events = service.events().list(
                calendarId='primary',
                timeMin=datetime.datetime.now().isoformat() + 'Z',
                timeMax=(datetime.datetime.now() + datetime.timedelta(days=30)).isoformat() + 'Z',
                q=title,
                singleEvents=True
            ).execute().get('items', [])
            
            if duplicate_events:
                message = f"🟡 You already have a similar event: '{title}'. Do you want to create another one?"
                add_to_conversation(task, message)
                return render_template('index.html', message=message, upcoming=upcoming_events,
                                     conversation=conversation_history)
            
            # Create the event
            event = create_calendar_event(service, title, start_time, end_time)
            
            success_message = f"✅ Scheduled '{title}' on {start_time.strftime('%A, %B %d')} at {start_time.strftime('%I:%M %p')} for {duration}"
            message = success_message
            add_to_conversation(task, success_message)
            
        except Exception as e:
            error_message = f"❌ Error: {str(e)}"
            message = error_message
            add_to_conversation(task, error_message)

    # Fetch upcoming events
    try:
        now = datetime.datetime.now()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        upcoming_events = events_result.get('items', [])
        
        # Format event times for display
        for event in upcoming_events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:  # DateTime format
                dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                event['formatted_time'] = dt.strftime('%A, %B %d at %I:%M %p')
            else:  # Date only
                dt = datetime.datetime.fromisoformat(start)
                event['formatted_time'] = dt.strftime('%A, %B %d (All day)')
                
    except Exception as e:
        print(f"Error fetching events: {e}")

    return render_template('index.html', 
                         message=message, 
                         upcoming=upcoming_events,
                         conversation=conversation_history,
                         needs_clarification=needs_clarification,
                         clarification_question=clarification_question)

@main.route('/clear_conversation', methods=['POST'])
def clear_conversation():
    """Clear conversation history"""
    session.pop('conversation_history', None)
    return redirect(url_for('main.index'))

@main.route('/login')
def login():
    session.clear()  # Clear any existing session
    flow = get_flow()
    auth_url, _ = flow.authorization_url(prompt='consent')
    return redirect(auth_url)

@main.route('/oauth2callback')
def oauth2callback():
    try:
        flow = get_flow()
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        session["credentials"] = pickle.dumps(creds).hex()
        return redirect(url_for('main.index'))
    except Exception as e:
        return f"OAuth error: {str(e)}", 400

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))