import requests
import os
import datetime
import dateparser

TOGETHER_API_KEY = os.getenv("8b40d4ef3eb45e2d520e191274284bef55114e2613f65b87507aa62ea488e8c7")  # safer than hardcoding

def call_deepseek(task_prompt):
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""Extract the task, duration (in minutes), and time from this user input.
Respond ONLY in JSON like:
{{"title": "...", "duration_minutes": ..., "start_time": "YYYY-MM-DD HH:MM"}}

User input: "{task_prompt}"
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant for scheduling tasks."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

        raw_text = result["choices"][0]["message"]["content"]

        import json
        data = json.loads(raw_text)

        title = data["title"]
        duration = datetime.timedelta(minutes=data["duration_minutes"])
        start_time = dateparser.parse(data["start_time"])

        return title, start_time, duration

    except Exception as e:
        print("DeepSeek parsing failed:", e)
        return None, None, None
