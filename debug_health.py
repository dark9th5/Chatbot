import requests
import time

url = "http://localhost:8000/api/health"

print(f"Checking health at {url}...")
try:
    start = time.time()
    response = requests.get(url, timeout=5)
    end = time.time()
    print(f"Status: {response.status_code}")
    print(f"Time: {end - start:.2f}s")
    print("Response:", response.text)
except Exception as e:
    print(f"Error: {e}")
