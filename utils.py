import json, calendar, os, requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

MESSARI_API_KEY_TYPE = "MESSARI_API_KEY_0"

load_dotenv()

# Utility to get timestamp in milliseconds for date X days ago (default: 30 days ago)
def timestamp_since(days=30):
    # Current UTC time
    now = datetime.now()

    date_after = now - timedelta(days)

    # Convert to milliseconds
    timestamp_ms = int(calendar.timegm(date_after.timetuple()) * 1000)

    return timestamp_ms

# Helper function to retrieve cached data or mock inputs for testing/debugging
def cache(data):
    if data == "req_from_news_intent":
        with open("data/json/intent_query.json", "r") as f:
            req_from_intent = json.load(f)
        return req_from_intent
    elif data in ["user_input", "llm_output", "prompt_system", "prompt_user", "prompt_insight", "prompt_deepthink","deepthink_response2"]:
        with open(f"data/txt/{data}.txt", "r", encoding="utf-8") as f:
            output = f.read()
        return output
    else:
        raise Exception(f'{data} request failed!')

# Mock implementation to simulate external data provider API configuration  
def mock_data_provider_api(file="data/json/mock.json"):
    with open(file, "r") as f:
        data_provider = json.load(f)
    return data_provider

# Core function to call LLM service (OpenAI or Messari)
def call_llm(
    prompt_messages: list,
    url: str = None,
    api_key_type: str = None,
    service: str = "openai"  # options: "openai" or "messari"
) -> str:
    if service == "messari":
        url = url or "https://api.messari.io/ai/openai/chat/completions"
        api_key_type = api_key_type or "MESSARI_API_KEY_0"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-MESSARI-API-KEY": os.getenv(api_key_type)
        }
        payload = {
            "verbosity": "balanced",
            "response_format": "plaintext", 
            "inline_citations": True,
            "stream": True,
            "messages": prompt_messages
        }
    elif service == "openai":
        url = url or "https://api.openai.com/v1/chat/completions"
        api_key_type = api_key_type or "OPENAI_API_KEY"
        headers = {
            "Authorization": f"Bearer {os.getenv(api_key_type)}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",  # or "gpt-3.5-turbo"
            "messages": prompt_messages,
            "temperature": 0.7,
            "stream": True
        }
    else:
        raise ValueError(f"Unsupported service: {service}")

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        res_txt = ""
        for line in response.iter_lines():
            if line:
                if line.startswith(b"data: "):
                    line = line[len(b"data: "):]
                if line == b"[DONE]":
                    break
                if not line.strip().startswith(b"{"):
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    delta = chunk["choices"][0]["delta"]
                    if "content" in delta:
                        res_txt += delta["content"]
                except json.JSONDecodeError:
                    print("Could not parse line:", line)
    else:
        raise Exception(f"Error {response.status_code} - in calling {service}: {response.text}")
    return res_txt
