# How to Run SmartShop

This guide covers how to set up and run the SmartShop agentic e-commerce project.

## Prerequisites

- **Python 3.9+** - Required for the backend
- **pip** - Python package manager
- **Node.js 16+** - Required for frontend (if running locally)
- **npm** - Node package manager
- **Meta Developer Account** - For Facebook/Instagram integration
- **OpenAI API Key** - For LLM functionality
- **WhatsApp Business Account** - For WhatsApp integration (optional)

## Installation

### 1. Clone the Repository

```bash
cd /home/ujjwal/codeagent/new/agentic_ecommerce_project
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies (if running locally)

```bash
cd apps/customer
npm install
cd ../owner
npm install
cd ../..
```

## Configuration

### 1. Create Environment File

Copy the example environment file:

```bash
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` and add your credentials:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIM=1536

# Database
DB_PATH=database/smartshop.db
DB_IMAGES_DIR=database/images
USER_IMAGES_DIR=uploads/user_images
TRYON_DIR=uploads/tryon_outputs

# Meta/Facebook/Instagram Unified Configuration
META_APP_ID=your_meta_app_id
META_APP_SECRET=your_meta_app_secret
META_ACCESS_TOKEN=your_meta_access_token
META_VERIFY_TOKEN=smartshop-webhook

# Facebook Page
FB_PAGE_ID=your_facebook_page_id
FB_PAGE_ACCESS_TOKEN=optional_use_meta_token_instead
FB_GRAPH_VERSION=v24.0

# Instagram Business Account
IG_USER_ID=your_instagram_business_account_id

# WhatsApp Business API (Optional)
WHATSAPP_API_TOKEN=your_whatsapp_api_token
WHATSAPP_PHONE_NUMBER_ID=your_whatsapp_phone_number_id

# Weather API (Optional)
OPENWEATHER_API_KEY=your_openweather_api_key

# Auto-reply Messages
DM_AUTO_REPLY="Thanks for your message! We'll get back to you soon."
COMMENT_AUTO_REPLY="Thanks for your comment! 🙌"

# Channel Feature Flags
ENABLE_FB_MESSENGER=true
ENABLE_INSTAGRAM=true
ENABLE_WHATSAPP=false
ENABLE_VOICE=true

# API URLs
CUSTOMER_API_URL=http://localhost:8000
OWNER_API_URL=http://localhost:8000
```

### 3. Get Meta Credentials

#### Step 1: Create Meta App
1. Go to [Meta Developers](https://developers.facebook.com/)
2. Create a new app
3. Add **Messenger** product for Facebook
4. Add **Instagram** product for Instagram
5. Note down `App ID` and `App Secret`

#### Step 2: Get Facebook Page Access Token
1. Create a Facebook Page for your business
2. In Meta App Dashboard → Messenger → Settings
3. Generate a Page Access Token
4. Note down `Page ID` and `Page Access Token`

#### Step 3: Get Instagram Business Account ID
1. Connect your Instagram Business Account to the Facebook Page
2. In Meta App Dashboard → Instagram → Basic Display
3. Note down your Instagram User ID

#### Step 4: Generate Long-Lived Access Token
1. Use the Page Access Token to generate a long-lived token
2. This token lasts 60 days and can be refreshed
3. Set this as `META_ACCESS_TOKEN`

### 4. Initialize Database

The database will be automatically created on first run, but you can initialize it manually:

```bash
python -c "import database; database.init_db()"
```

### 5. Add Sample Products (Optional)

You can add products via the owner dashboard or directly to the database:

```bash
python -c "
import database
database.add_product(
    name='Red T-Shirt',
    price=999,
    description='Comfortable cotton t-shirt in red',
    category='tshirt',
    image_url='database/images/red_tshirt.jpg'
)
"
```

## Running the Server

### Development Mode (with Auto-Reload)

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The server will start on `http://localhost:8000`

### Verify Server is Running

Visit `http://localhost:8000/` in your browser. You should see:

```json
{
  "app": "SmartShop",
  "version": "2.0",
  "status": "running"
}
```

## Running the Frontend

### Customer App

```bash
cd apps/customer
npm run dev
```

The customer app will run on `http://localhost:3000` (or another port if 3000 is busy)

### Owner App

```bash
cd apps/owner
npm run dev
```

The owner app will run on `http://localhost:3001` (or another port if 3001 is busy)

## Setting Up Webhooks

### Local Development with Ngrok

Since Meta webhooks require a public HTTPS URL, use ngrok for local development:

#### Install Ngrok

Download from [ngrok.com](https://ngrok.com/)

#### Start Ngrok

```bash
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

#### Configure Meta Webhooks

**Facebook Messenger:**
1. Go to Meta App Dashboard → Messenger → Webhooks
2. Set Callback URL: `https://your-ngrok-url.ngrok.io/api/facebook/webhook`
3. Set Verify Token: `smartshop-webhook` (or your `META_VERIFY_TOKEN`)
4. Subscribe to fields: `messages`, `messaging_postbacks`

**Instagram:**
1. Go to Meta App Dashboard → Instagram → Webhooks
2. Set Callback URL: `https://your-ngrok-url.ngrok.io/api/instagram/webhook`
3. Set Verify Token: `smartshop-webhook` (or your `META_VERIFY_TOKEN`)
4. Subscribe to fields: `messages`, `comments`, `mentions`

**WhatsApp:**
1. Go to Meta App Dashboard → WhatsApp → Configuration
2. Set Webhook URL: `https://your-ngrok-url.ngrok.io/api/whatsapp/webhook`
3. Set Verify Token: `smartshop-webhook` (or your `META_VERIFY_TOKEN`)

### Production Deployment

For production, use your actual domain:

- Facebook: `https://yourdomain.com/api/facebook/webhook`
- Instagram: `https://yourdomain.com/api/instagram/webhook`
- WhatsApp: `https://yourdomain.com/api/whatsapp/webhook`

Ensure your server has SSL/TLS certificates (Let's Encrypt recommended).

## Testing the Integration

### Test Web Chat (Web Channel)

1. Open customer app at `http://localhost:3000`
2. Type a message: "show me red tshirts"
3. You should see product results

### Test Facebook Messenger

1. Go to your Facebook Page
2. Click "Message" button
3. Send a message: "show me blue jackets"
4. You should receive a response from the bot

### Test Instagram DM

1. Go to your Instagram Business Account
2. Send a DM: "show me sarees"
3. You should receive a response from the bot

### Test Instagram Comments

1. Post on Instagram
2. Leave a comment
3. The bot should auto-reply with `COMMENT_AUTO_REPLY`

### Test WhatsApp

1. Send a message to your WhatsApp Business number
2. Type: "search shirts"
3. You should receive a response

### Test Post Publishing

#### Facebook Post

```bash
curl -X POST http://localhost:8000/api/facebook/post \
  -H "Content-Type: application/json" \
  -d '{
    "caption": "Check out our new collection!"
  }'
```

#### Instagram Post

```bash
curl -X POST http://localhost:8000/api/instagram/post \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/product.jpg",
    "caption": "New arrival! #fashion"
  }'
```

## Common Issues and Troubleshooting

### Issue: "Module not found" errors

**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: Database locked

**Solution:**
```bash
rm database/smartshop.db
python -c "import database; database.init_db()"
```

### Issue: Webhook verification fails

**Solution:**
- Check that `META_VERIFY_TOKEN` matches in both `.env` and Meta Dashboard
- Ensure webhook URL is publicly accessible (use ngrok for local dev)
- Check server logs for verification attempts

### Issue: Meta API returns "Invalid access token"

**Solution:**
- Verify `META_ACCESS_TOKEN` is valid
- Check if token has expired (60-day lifecycle)
- Generate a new long-lived token if needed
- Ensure token has required permissions

### Issue: SSE streaming not working

**Solution:**
- Check that `interface_mode` parameter is being passed from frontend
- Verify channel capabilities are being resolved correctly
- Check browser console for SSE connection errors
- Ensure CORS is properly configured in `main.py`

### Issue: Images not loading

**Solution:**
- Ensure image directories exist and have proper permissions
- Check that `DB_IMAGES_DIR`, `USER_IMAGES_DIR`, `TRYON_DIR` paths are correct
- Verify static file mounts are configured in `main.py`

### Issue: OpenAI API errors

**Solution:**
- Verify `OPENAI_API_KEY` is valid and has credits
- Check that `OPENAI_MODEL` is available in your account
- Ensure network can reach OpenAI API

## Development Workflow

### Making Changes

1. Edit code
2. Server auto-reloads (development mode)
3. Test changes
4. Commit to git

### Adding New Agents

1. Create agent file in `agents/` or `specialist_agents/`
2. Add intent to `orchestrator.py`
3. Add routing logic in `_build_plan_inner()`
4. Test with various queries

### Adding New Channels

1. Add channel capabilities to `channels/capabilities.py`
2. Create route handler in `routes/`
3. Register router in `main.py`
4. Add environment variables to `config.py`
5. Test webhook and message handling

## Deployment

### Using Docker (Recommended for Production)

```bash
# Build image
docker build -t smartshop .

# Run container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e META_ACCESS_TOKEN=your_token \
  --env-file .env \
  smartshop
```

### Using systemd (Linux)

Create `/etc/systemd/system/smartshop.service`:

```ini
[Unit]
Description=SmartShop API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/agentic_ecommerce_project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable smartshop
sudo systemctl start smartshop
```

### Using Nginx Reverse Proxy

Configure Nginx:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable SSL with Let's Encrypt:

```bash
sudo certbot --nginx -d yourdomain.com
```

## Monitoring and Logging

### View Logs

Logs are written to console. To save to file:

```bash
python main.py > logs/app.log 2>&1
```

### Check Database

```bash
sqlite3 database/smartshop.db
.tables
SELECT * FROM products LIMIT 10;
```

### Health Check

```bash
curl http://localhost:8000/api/health
```

## Performance Optimization

### Use Redis for Session Storage (Optional)

For production with high traffic, consider using Redis instead of SQLite for session management.

### Enable Caching

Add Redis or Memcached for caching LLM responses and product searches.

### Load Balancing

Use multiple workers with uvicorn:

```bash
uvicorn main:app --workers 4
```

## Security Best Practices

1. **Never commit `.env` file** to version control
2. **Use strong verify tokens** for webhooks
3. **Rotate access tokens** periodically
4. **Enable rate limiting** on public endpoints
5. **Use HTTPS** in production
6. **Keep dependencies updated** with `pip install --upgrade`
7. **Monitor logs** for suspicious activity

## Support

For issues or questions:
- Check `context.md` for project documentation
- Review logs for error messages
- Verify environment variables are set correctly
- Ensure Meta app has required permissions

## Next Steps

After successfully running the project:

1. Add your product catalog to the database
2. Customize auto-reply messages
3. Set up monitoring and alerts
4. Configure analytics tracking
5. Test all channel integrations
6. Deploy to production
7. Set up CI/CD pipeline
