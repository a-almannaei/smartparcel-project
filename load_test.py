import urllib.request
import json
import concurrent.futures
import time

API_URL = "http://127.0.0.0:8080/health"
TOTAL_REQUESTS = 50

def send_request():
    try:
        req = urllib.request.Request(API_URL, method="GET")
        with urllib.request.urlopen(req) as response:
            return response.status
    except Exception as e:
        return str(e)

print(f"Starting load test with {TOTAL_REQUESTS} concurrent requests...")
start_time = time.time()

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(lambda _: send_request(), range(TOTAL_REQUESTS)))

end_time = time.time()

successes = results.count(200)
print(f"Test Complete in {round(end_time - start_time, 2)} seconds!")
print(f"Successful Requests: {successes}/{TOTAL_REQUESTS}")