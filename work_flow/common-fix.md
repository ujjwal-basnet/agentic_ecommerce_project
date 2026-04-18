# Common Fixes — Instagram Webhook Setup

## Problem: "The callback URL or verify token couldn't be validated"

### Root Causes & Fixes Applied

---

### Fix 1: Verify Token Mismatch

**Problem:** The `VERIFY_TOKEN` in the server code (`"my_verify_token"`) did not match the token entered in Meta's webhook dashboard (`"adadadas"`). Meta sends the token in a GET request and expects the server to echo back the `hub.challenge` value — if tokens don't match, the server returns 403 and verification fails.

**Fix:** Updated `VERIFY_TOKEN` default in `main.py`, `run_server.py`, and `start.sh` to match whatever token is set in Meta's dashboard.

In `main.py`:
```python
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "adadadas")
```

---

### Fix 2: Server Not Restarted After Token Change

**Problem:** Changing the token in the file does not take effect while the old server process is still running. The old process keeps the old token in memory.

**Fix:** Kill the running server process and restart it after any code/token change.

```bash
pkill -f "uvicorn main:app"
VERIFY_TOKEN=adadadas ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

---

### Fix 3: ngrok Free Tier Browser Interstitial

**Problem:** ngrok's free tier injects an HTML interstitial warning page for requests that look like browser traffic. Meta's webhook verification request may hit this page instead of your actual server, causing validation to fail.

**Fix:** Added middleware in `main.py` that sets the `ngrok-skip-browser-warning: true` response header on every response. This tells ngrok to skip the interstitial and forward requests directly to the server.

```python
from starlette.middleware.base import BaseHTTPMiddleware

class NgrokMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

app.add_middleware(NgrokMiddleware)
```

---

## How to Test the Webhook Manually

Before clicking "Verify and Save" in Meta's dashboard, test your endpoint yourself:

```bash
curl "https://<your-ngrok-url>/webhook?hub.mode=subscribe&hub.verify_token=adadadas&hub.challenge=test123"
```

Expected response: `test123`

If you get `test123` back, the server is set up correctly and Meta's verification should pass.

---

## Note on "App must be in published state"

This is just an informational warning from Meta. In development mode, webhooks still work for accounts that have the **Tester** or **Developer** role on the app. This warning only matters when you want webhooks from real public users, which requires going through Meta's App Review process.
