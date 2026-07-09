#import "../../template.typ": title-slide, slide-layout, divider-slide

#title-slide(
  title: "Multi-Channel Integration",
  subtitle: "Part 3: Meta Webhooks & Messenger Gateway",
  author: "researchcontentlab@gmail.com",
  project: "project-ba58c036-070e-438e-b8b"
)

#pagebreak()

#show: slide-layout.with(title: "Webhook Architecture Flow", section: "Integration Overview")

#grid(
  columns: (1.2fr, 0.8fr),
  gutter: 1.5em,
  [
    - FastAPI webhook routers handle inbound DMs from Facebook and Instagram.
    - Path: `api/routes/facebook.py` & `api/routes/instagram.py`
    - High-level flow:
      1. Facebook user sends a message.
      2. Meta forwards payload to FastAPI webhook.
      3. Webhook parses text and executes `engine.run_text()`.
      4. Webhook posts response back to Meta Graph API.
  ],
  [
    #rect(fill: rgb("#EFF6FF"), inset: 1em, radius: 5pt)[
      *Active Subscriptions:*
      - `messages`
      - `messaging_postbacks`
      - `message_reads`
      - `message_deliveries`
    ]
  ]
)

#pagebreak()

#show: slide-layout.with(title: "Secure Webhook Signature Validation", section: "Webhook Security")

- Webhook endpoints verify Meta signatures (`x-hub-signature-256`) to block fraudulent payloads.
- Computes SHA256 HMAC of the request body using `META_APP_SECRET`.

```python
body = await request.body()
signature = request.headers.get("x-hub-signature-256", "")
expected = "sha256=" + hmac.new(
    META_APP_SECRET.encode(), body, hashlib.sha256
).hexdigest()

if not hmac.compare_digest(signature, expected):
    return PlainTextResponse("Forbidden", status_code=403)
```

#pagebreak()

#show: slide-layout.with(title: "Meta Messaging API Client", section: "Response Client")

- Core module: `api/routes/facebook.py`
- Sends responses back to Messenger asynchronously using the *aiohttp* HTTP client.

*API Send Code:*
```python
async def send_messenger_message(recipient_id: str, text: str):
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return resp.status == 200
```
