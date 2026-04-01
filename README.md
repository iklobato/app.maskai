# maskai

MCP server for email intelligence. Connect Gmail and Outlook accounts and ask AI assistants questions about your inbox.

## Features

- **MCP Server**: Natural language email search for AI assistants (Claude, GPT, etc.)
- **Email Integration**: Gmail and Microsoft Outlook via OAuth
- **Semantic Search**: Vector embeddings for natural language queries
- **Subscription Tiers**: Basic ($9), Pro ($29), Enterprise ($99)

## Prerequisites

- [DigitalOcean Account](https://digitalocean.com)
- [Google Cloud Console](https://console.cloud.google.com/) project
- [Azure Portal](https://portal.azure.com/) account
- [Stripe Account](https://stripe.com/)

---

## Local Development

```bash
# 1. Install dependencies
uv sync

# 2. Copy environment
cp .env.example .env

# 3. Configure credentials (see Configuration section below)

# 4. Start database with Docker
docker compose up db -d

# 5. Run migrations
alembic upgrade head

# 6. Start server
uvicorn backend.main:app --reload

# App runs at http://localhost:8000
```

---

## DigitalOcean Deployment

### 1. Create Managed PostgreSQL Database

1. In DigitalOcean dashboard, go to **Databases**
2. Click **Create Database**
3. Choose **PostgreSQL** with **pgvector** enabled
4. Select closest region, choose plan
5. Under **Connection Details**, note:
   - Host (URI)
   - Port (5432)
   - User (doadmin)
   - Password
   - Database name

6. Create a new database user:
   ```sql
   CREATE USER maskai WITH PASSWORD 'your-password';
   CREATE DATABASE maskai OWNER maskai;
   GRANT ALL PRIVILEGES ON DATABASE maskai TO maskai;
   ```

7. Enable **pgvector** extension:
   ```sql
   CONNECT TO maskai;
   CREATE EXTENSION vector;
   ```

8. Add firewall rule to allow app platform access (or use private networking)

### 2. Configure OAuth for Production

#### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Navigate to **APIs & Services > Credentials**
4. Click **Create Credentials > OAuth client ID**
5. Application type: **Web application**
6. Add authorized redirect URIs:
   ```
   https://your-app.ondigitalocean.app/api/auth/google/callback
   https://your-app.ondigitalocean.app/api/auth/microsoft/callback
   ```
   Replace with your actual DigitalOcean app URL
7. Copy **Client ID** and **Client Secret**

#### Microsoft OAuth

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Azure Active Directory > App registrations**
3. Click **New registration**
4. Name: `maskai`
5. Supported account types: **Personal Microsoft accounts**
6. Redirect URI: **Web**, add:
   ```
   https://your-app.ondigitalocean.app/api/auth/microsoft/callback
   ```
7. Go to **Certificates & secrets > New client secret**, copy value
8. Go to **Overview**, copy **Application (client) ID**

### 3. Create DigitalOcean App

1. In DigitalOcean dashboard, go to **Apps**
2. Click **Create App**
3. Choose **GitHub** as source
4. Select your repository and branch
5. For **App Spec**, select `do/app.yaml` or configure manually:
   ```yaml
   name: maskai
   region: nyc
   static_sites:
     - build_command: ""
       environment_slug: ""
       http_port: 8000
       index_document: index.html
       name: app
       output_dir: ""
       routes:
         - path: /
   workers:
     - build_command: uv sync
       environment_slug: python
       envs:
         - key: WEB_CONCURRENCY
           value: "4"
       github:
           branch: main
           deploy_on_push: true
           repo: your-username/maskai
       http_port: 8000
       instance_count: 1
       instance_size_slug: basic-xxs
       name: web
       run_command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```

6. Click **Next**

### 4. Configure Environment Variables

In DigitalOcean App Platform, add these environment variables:

| Key | Value | Notes |
|-----|-------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://maskai:PASSWORD@HOST:PORT/maskai` | Use your managed DB connection string |
| `DATABASE_URL_SYNC` | `postgresql://maskai:PASSWORD@HOST:PORT/maskai` | Same, without asyncpg prefix |
| `JWT_SECRET_KEY` | Generate 64-char random string | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | Fernet key | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console | |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console | |
| `GOOGLE_REDIRECT_URI` | `https://your-app.ondigitalocean.app/api/auth/google/callback` | |
| `MICROSOFT_CLIENT_ID` | From Azure Portal | |
| `MICROSOFT_CLIENT_SECRET` | From Azure Portal | |
| `MICROSOFT_REDIRECT_URI` | `https://your-app.ondigitalocean.app/api/auth/microsoft/callback` | |
| `STRIPE_SECRET_KEY` | `sk_live_xxx` | Use live keys in production |
| `STRIPE_WEBHOOK_SECRET` | `whsec_xxx` | From Stripe Dashboard |
| `STRIPE_PRICE_BASIC` | `price_xxx` | From Stripe Dashboard |
| `STRIPE_PRICE_PRO` | `price_xxx` | From Stripe Dashboard |
| `STRIPE_PRICE_ENTERPRISE` | `price_xxx` | From Stripe Dashboard |
| `APP_URL` | `https://your-app.ondigitalocean.app` | Your app's URL |
| `ENV` | `production` | |

### 5. Configure Stripe Webhooks

1. In Stripe Dashboard, go to **Webhooks**
2. Click **Add endpoint**
3. Endpoint URL: `https://your-app.ondigitalocean.app/api/webhooks/stripe`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Copy the **Webhook Secret** (`whsec_xxx`)

### 6. Deploy

1. Click **Create Resources**
2. Wait for build to complete
3. Note your app's URL (e.g., `maskai-abc123.ondigitalocean.app`)
4. Update OAuth redirect URIs if needed with the actual URL
5. Test the deployment

---

## Configuration

### Environment Variables Reference

```env
# Database (PostgreSQL with pgvector)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/maskai
DATABASE_URL_SYNC=postgresql://user:pass@host:5432/maskai

# JWT Authentication
JWT_SECRET_KEY=your-64-char-random-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_MINUTES=30
JWT_REFRESH_DAYS=7

# Google OAuth
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
GOOGLE_REDIRECT_URI=https://your-app.ondigitalocean.app/api/auth/google/callback

# Microsoft OAuth
MICROSOFT_CLIENT_ID=xxx
MICROSOFT_CLIENT_SECRET=xxx
MICROSOFT_REDIRECT_URI=https://your-app.ondigitalocean.app/api/auth/microsoft/callback

# Stripe
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_BASIC=price_xxx
STRIPE_PRICE_PRO=price_xxx
STRIPE_PRICE_ENTERPRISE=price_xxx

# Encryption
ENCRYPTION_KEY=xxx (Fernet key)

# App
APP_URL=https://your-app.ondigitalocean.app
ENV=production
```

### Generating Secrets

```bash
# JWT Secret (64 chars)
openssl rand -hex 32

# Fernet Encryption Key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Development

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Lint
ruff check .

# Format
ruff format .
```

---

## Architecture

```
backend/
├── main.py              # FastAPI app + routes
├── auth.py              # JWT, passwords, API keys
├── config.py            # Settings
├── database.py          # SQLAlchemy models
├── sync.py             # Email sync + embeddings
├── mcp_server.py       # MCP tools
├── interfaces/          # Abstract base classes
│   ├── oauth_provider.py
│   ├── email_provider.py
│   ├── embedding_model.py
│   ├── vector_store.py
│   └── payment_provider.py
├── oauth/              # OAuth implementations
├── email/              # Email providers
├── payments/           # Payment providers
├── embeddings/         # Embedding models
└── vector/             # Vector stores
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/auth/register | Create account |
| POST | /api/auth/login | Login |
| GET | /api/auth/me | Get current user |
| GET | /api/auth/google/start | Start Google OAuth |
| GET | /api/auth/google/callback | Google OAuth callback |
| GET | /api/auth/microsoft/start | Start Microsoft OAuth |
| GET | /api/auth/microsoft/callback | Microsoft OAuth callback |
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

---

## MCP Tools

- `list_accounts` - List connected email accounts
- `search_emails` - Natural language email search
- `get_email` - Get full email details with body
- `get_recent_emails` - Recent inbox emails
