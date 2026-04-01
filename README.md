# maskai

MCP server for email intelligence. Connect Gmail and Outlook accounts and ask AI assistants questions about your inbox.

## Features

- **MCP Server**: Natural language email search for AI assistants (Claude, GPT, etc.)
- **Email Integration**: Gmail and Microsoft Outlook via OAuth
- **Semantic Search**: Vector embeddings for natural language queries
- **Subscription Tiers**: Basic ($9), Pro ($29), Enterprise ($99)

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Copy environment
cp .env.example .env

# 3. Configure credentials (see below)
# 4. Edit .env with your values

# 5. Start database (SQLite for local, Docker for production)
# Local SQLite (no setup needed):
export DATABASE_URL=sqlite+aiosqlite:///./maskai.db
export DATABASE_URL_SYNC=sqlite:///./maskai.db

# Or with Docker:
docker compose up -d

# 6. Run migrations
alembic upgrade head

# 7. Start server
uvicorn backend.main:app --reload
```

## Configuration

### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to **APIs & Services > Credentials**
4. Click **Create Credentials > OAuth client ID**
5. Application type: **Web application**
6. Add authorized redirect URI: `http://localhost:8000/api/auth/google/callback`
7. Copy **Client ID** and **Client Secret** to `.env`:
   ```
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
   ```

### Microsoft OAuth

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Azure Active Directory > App registrations**
3. Click **New registration**
4. Name: `maskai`
5. Supported account types: **Personal Microsoft accounts** (or multi-tenant as needed)
6. Redirect URI: **Web**, then add: `http://localhost:8000/api/auth/microsoft/callback`
7. After creation, go to **Certificates & secrets**
8. Click **New client secret**, copy the value
9. Go to **Overview**, copy **Application (client) ID**
10. Add to `.env`:
    ```
    MICROSOFT_CLIENT_ID=your-client-id
    MICROSOFT_CLIENT_SECRET=your-client-secret
    MICROSOFT_REDIRECT_URI=http://localhost:8000/api/auth/microsoft/callback
    ```

### Stripe

1. Create a [Stripe](https://stripe.com/) account
2. Go to **Developers > API keys**, copy test keys
3. Create products and prices in Stripe Dashboard
4. Set up webhooks: `https://your-domain.com/api/webhooks/stripe`
5. Add to `.env`:
   ```
   STRIPE_SECRET_KEY=sk_test_xxx
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   STRIPE_PRICE_BASIC=price_xxx
   STRIPE_PRICE_PRO=price_xxx
   STRIPE_PRICE_ENTERPRISE=price_xxx
   ```

### Other Variables

```env
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=your-64-char-secret

# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-key

DATABASE_URL=sqlite+aiosqlite:///./maskai.db
DATABASE_URL_SYNC=sqlite:///./maskai.db

APP_URL=http://localhost:8000
ENV=development
```

## Development

```bash
# Run tests
pytest

# Lint
ruff check .

# Format
ruff format .
```

## Architecture

```
backend/
├── main.py              # FastAPI app + routes
├── auth.py              # JWT, passwords, API keys
├── config.py            # Settings
├── database.py          # SQLAlchemy models
├── sync.py              # Email sync + embeddings
├── mcp_server.py        # MCP tools
├── interfaces/           # Abstract base classes
│   ├── oauth_provider.py
│   ├── email_provider.py
│   ├── embedding_model.py
│   ├── vector_store.py
│   └── payment_provider.py
├── oauth/              # OAuth implementations
│   ├── google_oauth.py
│   └── microsoft_oauth.py
├── email/              # Email providers
│   ├── gmail.py
│   └── outlook.py
├── payments/           # Payment providers
│   └── stripe_provider.py
├── embeddings/         # Embedding models
│   └── sentence_transformers.py
└── vector/             # Vector stores
    └── pgvector.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/auth/register | Create account |
| POST | /api/auth/login | Login |
| GET | /api/auth/me | Get current user |
| GET | /api/auth/google/start | Start Google OAuth |
| GET | /api/auth/google/callback | Google OAuth callback |
| GET | /api/accounts | List connected accounts |
| DELETE | /api/accounts/{id} | Disconnect account |
| POST | /api/keys | Generate API key |
| GET | /api/keys | List API keys |
| DELETE | /api/keys/{id} | Revoke API key |
| GET | /api/subscription | Get subscription |
| POST | /api/subscription/checkout | Create checkout |
| POST | /api/subscription/portal | Manage subscription |
| POST | /api/webhooks/stripe | Stripe webhooks |
| GET | /api/health | Health check |

## MCP Tools

- `list_accounts` - List connected email accounts
- `search_emails` - Natural language email search
- `get_email` - Get full email details with body
- `get_recent_emails` - Recent inbox emails
