"""
LLM API helpers for Groq.
Handles API calls with rate limiting and model fallback.
"""

import requests
import time

from config import GROQ_API_KEY, GROQ_MODEL_QUICK, GROQ_MODEL_FULL


def call_groq(messages, model=None, max_tokens=1024):
    """Call Groq API with the specified model."""
    if not model:
        model = GROQ_MODEL_QUICK
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    
    return response.json()["choices"][0]["message"]["content"]


def quick_summary_request(messages):
    """Make a quick summary request with fallback on rate limit."""
    try:
        return call_groq(messages, model=GROQ_MODEL_QUICK, max_tokens=512)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"  ⚠️  Rate limited on {GROQ_MODEL_QUICK}, trying groq/compound-mini...")
            time.sleep(1)
            return call_groq(messages, model="groq/compound-mini", max_tokens=512)
        raise


def full_summary_request(messages):
    """Make a full summary request with larger context."""
    try:
        return call_groq(messages, model=GROQ_MODEL_FULL, max_tokens=4096)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"  ⚠️  Rate limited on {GROQ_MODEL_FULL}, trying openai/gpt-oss-120b...")
            time.sleep(1)
            return call_groq(messages, model="openai/gpt-oss-120b", max_tokens=4096)
        raise
