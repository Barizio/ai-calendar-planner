import requests
import os
import datetime
import dateparser
import json
from typing import Tuple, Optional, Dict, Any

# Fix: Use proper env variable name
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

def call_deepseek(task_prompt: str, conversation_history: list = None) -> Tuple[Optional[str], Optional[datetime.datetime], Optional[datetime.timedelta], Optional[str]]:
    """
    Parse task using DeepSeek API with conversation context
    Returns: (title, start_time, duration, clarification_question)
    """
    if not TOGETHER_API_KEY:
        return None, None, None, "API key not configured"
    
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }

    # Build context-aware prompt
    context = ""
    if conversation_history:
        context = "\n".join([f"User: {msg['user']}\nAssistant: {msg['assistant']}" for msg in conversation_history[-3:]])
        context = f"Previous conversation:\n{context}\n\n"

    current_time = datetime.datetime.now()
    
    prompt = f"""You are an AI calendar assistant. Extract task details from user input.

{context}Current time: {current_time.strftime('%Y-%m-%d %H:%M')} (Lagos time)

RULES:
1. If input is clear, respond with JSON: {{"title": "...", "duration_minutes": ..., "start_time": "YYYY-MM-DD HH:MM", "status": "complete"}}
2. If unclear, ask for clarification: {{"status": "clarification", "question": "..."}}
3. For relative times (tomorrow, next week), calculate actual dates
4. Default duration is 60 minutes if not specified
5. Default time is next available business hour if not specified

Examples:
- "KPMG meeting tomorrow 5pm for 3 hours" → {{"title": "KPMG meeting", "duration_minutes": 180, "start_time": "2025-07-11 17:00", "status": "complete"}}
- "Meeting with John" → {{"status": "clarification", "question": "When would you like to schedule the meeting with John? Please specify date and time."}}

User input: "{task_prompt}"
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a helpful calendar assistant. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 200
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()

        raw_text = result["choices"][0]["message"]["content"].strip()
        
        # Extract JSON from response
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3]
        
        data = json.loads(raw_text)
        
        # Handle clarification requests
        if data.get("status") == "clarification":
            return None, None, None, data.get("question")
        
        # Parse successful response
        title = data.get("title", "").strip()
        duration_minutes = data.get("duration_minutes", 60)
        start_time_str = data.get("start_time", "")
        
        if not title:
            return None, None, None, "Could not extract task title. Please provide more details."
        
        # Parse start time
        start_time = None
        if start_time_str:
            try:
                start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                start_time = dateparser.parse(start_time_str)
        
        if not start_time:
            return None, None, None, "Could not understand the time. Please specify when you'd like to schedule this task."
        
        duration = datetime.timedelta(minutes=duration_minutes)
        
        return title, start_time, duration, None

    except requests.exceptions.RequestException as e:
        return None, None, None, f"Network error: {str(e)}"
    except json.JSONDecodeError as e:
        return None, None, None, f"Could not parse response. Please try rephrasing your request."
    except Exception as e:
        return None, None, None, f"Error processing request: {str(e)}"


def parse_natural_language(task_str: str) -> Tuple[Optional[str], Optional[datetime.datetime], Optional[datetime.timedelta]]:
    """
    Fallback local parser for common patterns
    """
    import re
    
    # Pattern: "task for X hours/minutes at time"
    pattern = r'(.+?)\s+for\s+(\d+)\s*(hours?|minutes?)\s+(.+)'
    match = re.search(pattern, task_str, re.IGNORECASE)
    
    if match:
        title = match.group(1).strip()
        duration_val = int(match.group(2))
        unit = match.group(3).lower()
        time_part = match.group(4).strip()
        
        # Convert duration
        if "hour" in unit:
            duration = datetime.timedelta(hours=duration_val)
        else:
            duration = datetime.timedelta(minutes=duration_val)
        
        # Parse time
        start_time = dateparser.parse(time_part, settings={'PREFER_DATES_FROM': 'future'})
        
        return title, start_time, duration
    
    # Pattern: "task tomorrow/today at time"
    pattern2 = r'(.+?)\s+(tomorrow|today|next\s+\w+)\s+(?:at\s+)?(.+)'
    match2 = re.search(pattern2, task_str, re.IGNORECASE)
    
    if match2:
        title = match2.group(1).strip()
        day_part = match2.group(2).strip()
        time_part = match2.group(3).strip()
        
        # Parse full time expression
        full_time = f"{day_part} {time_part}"
        start_time = dateparser.parse(full_time, settings={'PREFER_DATES_FROM': 'future'})
        
        # Default duration
        duration = datetime.timedelta(hours=1)
        
        return title, start_time, duration
    
    return None, None, None