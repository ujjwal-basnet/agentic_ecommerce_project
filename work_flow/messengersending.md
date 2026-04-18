# Messenger Sending — How We Fixed It

## What Was Working
- Server (FastAPI + ngrok) was running fine
- Webhook was receiving messages from Meta perfectly
- Bot could see "hi" from user

## What Was Broken — 3 Problems

---

### Problem 1: Wrong Access Token (User Token vs Page Token)

**Error:** `Application does not have the capability to make this API call` (code 3)

**Cause:** The token in `config.py` was a **User Access Token** (tied to Ujjwal Basnet the person).
To send messages via Messenger API, you need a **Page Access Token** (tied to the Ecom agent page).

**Fix:** Exchanged the user token for a page token using:
```
GET /me/accounts?access_token=<user_token>
```
This returns the page token for every page the user manages.
Updated `config.py` with the page token.

---

### Problem 2: Wrong API Endpoint

**Error:** Same `(#3) Application does not have the capability` error

**Cause:** The code was posting to:
```
/{IG_USER_ID}/messages
```
But IG_USER_ID was set to the Instagram account ID (`17841478601271445`).
For **Facebook Messenger**, the correct endpoint is:
```
/{PAGE_ID}/messages   →   /898369430036192/messages
```

**Fix:** Updated `reply_to_dm()` in `instagram_api.py` to use the Facebook Page ID (`898369430036192`) instead of the Instagram user ID.

---

### Problem 3: Bot Was Replying to Its Own Echo Messages

**Cause:** Meta sends "echo" events to the webhook when the bot itself sends a message.
The code was treating these echoes as new incoming messages and trying to reply again — causing a loop.

**Fix:** Added a check in `main.py` to skip messages where `is_echo = true`:
```python
is_echo = message.get("is_echo", False)
if sender_id and text and not is_echo and sender_id != recipient_id:
    # reply
```

---

## Final Result

- User sends "hi" to **Ecom agent** Facebook page
- Webhook receives it at `/webhook`
- Bot detects "hi" keyword
- Bot replies: **"Hello! 👋 How can I help you?"**
- Confirmed working in logs: `[api] DM sent to 34894948196787546`

---

## Token Notes

| Token Type | Used For | Endpoint |
|---|---|---|
| User Token | Checking identity, getting page list | `/me`, `/me/accounts` |
| Page Token | Sending messages, posting | `/{page_id}/messages` |

**Always use the Page Token for Messenger send API.**
The page token can be obtained from the user token via `/me/accounts`.
