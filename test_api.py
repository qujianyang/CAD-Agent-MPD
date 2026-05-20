"""
Direct NVIDIA API diagnostic test.
"""
import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("NVIDIA_API_KEY")
if not API_KEY:
    sys.exit("ERROR: set NVIDIA_API_KEY in your environment first.")

MODEL = os.environ.get("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-nano-8b-v1")

print("=" * 60)
print("DIRECT NVIDIA API TEST")
print("=" * 60)

url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "How to choose a right shock mount and base on what parameter? "}],
    "max_tokens": 60,
}

print(f"\nURL: {url}")
print(f"Model: {payload['model']}")
print("\nSending request...")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=120)
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except ValueError:
        print(f"Response (non-JSON):\n{response.text}")
except Exception as e:
    print(f"Error: {e}")
