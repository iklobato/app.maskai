# maskai

MCP server for email intelligence. Connect Gmail accounts and ask AI assistants questions about your inbox.

## Features

- **MCP Server**: Natural language email search for AI assistants (Claude, GPT, etc.)
- **Gmail Integration**: Connect Google accounts via OAuth
- **Semantic Search**: Vector embeddings for natural language queries
- **Subscription Tiers**: Basic ($9), Pro ($29), Enterprise ($99)

## Quick Start

```bash
# Copy environment
cp .env.example .env
# Edit .env with your credentials

# Start services
docker compose up -d

# Run migrations
alembic upgrade head

# Start development
uvicorn backend.main:app --reload
```

## Environment Variables

See `.env.example` for all required variables:

- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - Random 64-character secret
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - Google OAuth credentials
- `STRIPE_*` - Stripe API keys and price IDs
- `ENCRYPTION_KEY` - Fernet encryption key

## Development

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Lint
ruff check .
```

## Architecture

- `backend/main.py` - FastAPI app + all routes
- `backend/auth.py` - JWT, passwords, API keys, OAuth
- `backend/gmail.py` - Gmail API, embeddings, vector search
- `backend/stripe.py` - Payments
- `backend/mcp_server.py` - MCP tools

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/auth/register | Create account |
| POST | /api/auth/login | Login |
| GET | /api/auth/google/start | Start Google OAuth |
| GET | /api/accounts | List connected accounts |
| DELETE | /api/accounts/{id} | Disconnect account |
| POST | /api/keys | Generate API key |
| GET | /api/keys | List API keys |
| GET | /api/subscription | Get subscription |
| POST | /api/subscription/checkout | Create checkout |
| GET | /api/health | Health check |

## MCP Tools

- `list_accounts` - List connected email accounts
- `search_emails` - Natural language search
- `get_email` - Get full email details
- `get_recent_emails` - Recent inbox emails
