# SmartShop - AI-Powered E-Commerce Platform

An intelligent e-commerce platform with AI-powered shopping assistant, personalized recommendations, virtual try-on, and comprehensive owner dashboard.

## Features

### Customer Features
- **AI Shopping Assistant** - Chat with an AI concierge to search products, get recommendations, and manage your cart
- **Smart Product Search** - Semantic search powered by embeddings and ChromaDB vector database
- **Personalized Recommendations** - AI-driven product suggestions based on user preferences
- **Shopping Cart** - Full cart management with quantity controls
- **Virtual Try-On** - Upload your photo to virtually try on wearable products
- **Weather-Based Suggestions** - Get outfit recommendations based on current weather conditions

### Owner Dashboard Features
- **Analytics Dashboard** - View revenue, orders, top products, and category breakdowns
- **Product Management** - Add, view, and delete products from inventory
- **Stock Monitoring** - Track low-stock items and inventory levels
- **Facebook Integration** - Auto-post new products to Facebook page with images and descriptions

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLite** - Lightweight database for products, carts, and sessions
- **OpenAI** - GPT-4 for natural language understanding and responses
- **ChromaDB** - Vector database for semantic product search
- **SSE (Server-Sent Events)** - Real-time streaming responses

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling with custom Material Design theme
- **Recharts** - Analytics charts (Owner Dashboard)

## Project Structure

```
├── main.py                    # FastAPI entry point
├── config.py                  # Application configuration
├── database.py                # SQLite database layer
├── llm.py                     # OpenAI LLM integration
├── log.py                     # Logging utilities
├── mcp.py                     # Model Context Protocol handler
├── orchestrator.py            # Intent classification & planning
├── executor.py                # Plan execution engine
├── renderer.py                # SSE event rendering
├── session_memory.py          # Session conversation memory
│
├── agents/                    # AI agent implementations
│   ├── __init__.py
│   ├── cart.py               # Cart management agent
│   ├── owner.py              # Owner dashboard agent (Facebook integration)
│   ├── recommend.py          # Recommendation agent
│   ├── search.py             # Product search agent (ChromaDB)
│   └── weather.py            # Weather information agent
│
├── routes/                   # API route handlers
│   ├── __init__.py
│   ├── customer.py           # Customer-facing endpoints
│   └── owner.py              # Owner dashboard endpoints
│
├── database/                  # Static assets
│   └── images/               # Product images
│
├── apps/
│   ├── customer/             # Customer frontend (Next.js)
│   │   ├── src/
│   │   │   ├── app/         # App pages and layouts
│   │   │   │   ├── page.tsx
│   │   │   │   ├── layout.tsx
│   │   │   │   └── globals.css
│   │   │   ├── components/
│   │   │   │   └── genui/   # Dynamic UI components
│   │   │   │       ├── ProductList.tsx
│   │   │   │       ├── CartDrawer.tsx
│   │   │   │       ├── CartConfirmation.tsx
│   │   │   │       ├── RecommendGrid.tsx
│   │   │   │       ├── WeatherCard.tsx
│   │   │   │       ├── TryOnResult.tsx
│   │   │   │       └── Registry.tsx
│   │   │   └── lib/
│   │   │       └── api.ts   # API client
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── tailwind.config.ts
│   │   └── next.config.mjs
│   │
│   └── owner/               # Owner dashboard (Next.js)
│       ├── src/
│       │   ├── app/         # App pages and layouts
│       │   │   ├── page.tsx
│       │   │   ├── layout.tsx
│       │   │   └── globals.css
│       │   └── lib/
│       │       └── api.ts   # API client
│       ├── package.json
│       ├── tsconfig.json
│       ├── tailwind.config.ts
│       └── next.config.mjs
│
├── uploads/                   # User uploads
│   ├── user_images/          # Uploaded user photos
│   └── tryon_outputs/        # Virtual try-on results
│
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
└── .gitignore                # Git ignore rules
```

## API Endpoints

### Customer API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/cart` | Get cart items |
| POST | `/api/cart/add` | Add item to cart |
| POST | `/api/cart/update` | Update cart item quantity |
| POST | `/api/cart/remove` | Remove item from cart |
| POST | `/chat/stream` | AI chat with SSE streaming |
| POST | `/upload-photo` | Upload user photo for try-on |
| POST | `/clear-chat` | Clear conversation history |

### Owner API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/owner/analytics` | Dashboard analytics |
| GET | `/owner/products` | List all products |
| POST | `/owner/products/new` | Add new product |
| POST | `/owner/products/update` | Update product |
| POST | `/owner/products/delete` | Delete product |

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- OpenAI API key
- (Optional) OpenWeather API key for weather features
- (Optional) Facebook Page credentials for social posting

### Backend Setup

1. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys:
   # OPENAI_API_KEY=sk-your-key-here
   ```

4. **Run the backend:**
   ```bash
   uvicorn main:app --reload
   ```
   API available at: http://localhost:8000

### Frontend Setup

1. **Customer Frontend:**
   ```bash
   cd apps/customer
   npm install
   npm run dev
   ```
   Customer UI available at: http://localhost:3000

2. **Owner Dashboard:**
   ```bash
   cd apps/owner
   npm install
   npm run dev
   ```
   Owner Dashboard available at: http://localhost:3001

### Database Initialization

The SQLite database is automatically created on first run with sample product data including:
- T-shirts (Red, Blue, Black)
- Denim Jacket
- Black Midi Dress
- Sunglasses
- Saree

Product images are stored in `database/images/`.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 | Yes |
| `OPENAI_MODEL` | Model to use (default: gpt-4o-mini) | No |
| `OPENWEATHER_API_KEY` | OpenWeather API key | No |
| `FB_PAGE_ID` | Facebook Page ID for posting | No |
| `FB_PAGE_ACCESS_TOKEN` | Facebook Page Access Token | No |
| `DB_PATH` | Path to SQLite database | No |
| `CHROMA_DIR` | Path to ChromaDB directory | No |

## Usage

### Customer
1. Open http://localhost:3000
2. Chat with the AI assistant:
   - "Show me red shirts"
   - "Recommend something for summer"
   - "What's the weather in Kathmandu?"
   - "View my cart"
3. Browse products and add to cart
4. Upload photo for virtual try-on on wearable items

### Owner Dashboard
1. Open http://localhost:3001
2. View analytics on the Overview tab
3. Manage products on the Products tab
4. Add new products with images
5. Enable "Post to Facebook" to auto-share new products

## Development

### Running All Services
```bash
# Terminal 1 - Backend
source .venv/bin/activate
uvicorn main:app --reload

# Terminal 2 - Customer Frontend
cd apps/customer && npm run dev

# Terminal 3 - Owner Frontend
cd apps/owner && npm run dev
```

### Testing API Endpoints
```bash
# Health check
curl http://localhost:8000/api/health

# Get cart
curl "http://localhost:8000/api/cart?session_id=test123"

# Add to cart
curl -X POST http://localhost:8000/api/cart/add \
  -d "session_id=test123&product_name=Red+T-Shirt&price=20&quantity=1"

# Owner analytics
curl http://localhost:8000/owner/analytics
```

## License

MIT License
