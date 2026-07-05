import httpx
import sys
import time

url = "https://gamma-api.polymarket.com/events?limit=5"
print(f"Testing connectivity to: {url}")
start = time.time()
try:
    with httpx.Client(timeout=httpx.Timeout(8.0, connect=5.0)) as client:
        resp = client.get(url)
        print(f"Success! Status code: {resp.status_code}")
        print(f"Response (first 200 chars): {resp.text[:200]}")
except Exception as e:
    print(f"Failed! Exception type: {type(e).__name__}")
    print(f"Exception message: {e!r}")
finally:
    print(f"Time taken: {time.time() - start:.2f} seconds")
