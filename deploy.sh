#!/usr/bin/env bash
set -euo pipefail

# ===========================================
# maski AI - DigitalOcean Deployment Script
# ===========================================
# Uses the cheapest option: App Platform (free tier) or $4/mo Droplet
# 
# Usage:
#   ./deploy.sh app          # Deploy to App Platform
#   ./deploy.sh droplet      # Deploy to $4/mo Droplet with Docker
#   ./deploy.sh status       # Check deployment status
#   ./deploy.sh destroy      # Tear down deployment
# ===========================================

# Configuration
REGION="nyc"
APP_NAME="maskai"
REPO="your-username/maskai"  # Change this to your repo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if doctl is installed
check_doctl() {
    if ! command -v doctl &> /dev/null; then
        log_error "doctl is not installed. Install it: https://docs.digitalocean.com/reference/doctl/how-to/install/"
        exit 1
    fi
    
    # Check authentication
    if ! doctl account get &> /dev/null; then
        log_error "doctl not authenticated. Run: doctl auth init"
        exit 1
    fi
    
    log_info "doctl ready"
}

# ===========================================
# APP PLATFORM DEPLOYMENT
# ===========================================

deploy_app_platform() {
    log_info "Deploying to DigitalOcean App Platform..."
    
    # Check for required env vars
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL not set. Create a managed PostgreSQL database first."
        log_info "Or use: ./deploy.sh droplet (creates Droplet with Docker)"
        exit 1
    fi
    
    # Create app spec
    cat > /tmp/maskai-app.yaml << 'EOF'
name: maski
region: nyc
databases:
  - engine: PG
    name: maski-db
    version: "16"
workers:
  - build_command: uv sync
    environment_slug: python
    github:
      branch: main
      deploy_on_push: true
      repo: REPO_PLACEHOLDER
    http_port: 8000
    instance_count: 1
    instance_size_slug: basic-xxs
    name: web
    run_command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envs:
      - key: DATABASE_URL
        value: "{{ database.JUMP_LINK }}"
      - key: DATABASE_URL_SYNC
        value: "{{ database.JUMP_LINK }}"
EOF

    # Replace placeholder
    sed -i "s|REPO_PLACEHOLDER|${REPO}|g" /tmp/maskai-app.yaml
    
    log_info "Creating App Platform app..."
    doctl apps create --spec /tmp/maskai-app.yaml
    
    log_info "App created! Configure environment variables in the dashboard:"
    log_info "  1. Go to https://cloud.digitalocean.com/apps"
    log_info "  2. Select your app"
    log_info "  3. Add environment variables (see README.md)"
    
    rm /tmp/maskai-app.yaml
}

# ===========================================
# DROPLET DEPLOYMENT ($4/mo)
# ===========================================

deploy_droplet() {
    log_info "Deploying to $4/mo Droplet with Docker..."
    
    # Droplet configuration
    DROPLET_NAME="maskai-server"
    IMAGE="docker-20-04"  # Docker on Ubuntu 20.04
    SIZE="s-1vcpu-1gb"   # $4/month
    SSH_KEYS=""  # Add your SSH key fingerprint here, or leave empty
    
    # User data script to set up Docker and run the app
    USER_DATA=$(cat << 'SCRIPT'
#!/bin/bash
set -e

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y docker.io docker-compose

# Create app directory
mkdir -p /app
cd /app

# Clone repo (you'll need to set this up or use a volume)
# For now, we'll create a minimal setup

# Create docker-compose.yml
cat > /app/docker-compose.yml << 'EOF'
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: maski
      POSTGRES_USER: maski
      POSTGRES_PASSWORD: maski
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U maski -d maski"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  pgdata:
EOF

# Create .env template
cat > /app/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://maskai:maskai@db:5432/maskai
DATABASE_URL_SYNC=postgresql://maskai:maskai@db:5432/maskai
JWT_SECRET_KEY=CHANGE_THIS_to_random_64_chars
ENCRYPTION_KEY=CHANGE_THIS_to_fernet_key
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://YOUR_IP/api/auth/google/callback
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_REDIRECT_URI=http://YOUR_IP/api/auth/microsoft/callback
STRIPE_SECRET_KEY=sk_test_
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_BASIC=
STRIPE_PRICE_PRO=
STRIPE_PRICE_ENTERPRISE=
APP_URL=http://YOUR_IP
ENV=production
EOF

# Pull and start services
cd /app
docker compose pull
docker compose up -d --build

# Run migrations
docker compose exec app alembic upgrade head

# Enable UFW and allow only 8000
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 8000/tcp
ufw --force enable

echo "Setup complete! Access at http://$(curl -s ifconfig.me):8000"
SCRIPT

    # Create droplet
    log_info "Creating Droplet: $DROPLET_NAME"
    
    DOCTL_CMD="doctl compute droplet create $DROPLET_NAME --region $REGION --size $SIZE --image $IMAGE --wait"
    
    if [[ -n "$SSH_KEYS" ]]; then
        DOCTL_CMD="$DOCTL_CMD --ssh-keys $SSH_KEYS"
    fi
    
    DOCTL_CMD="$DOCTL_CMD --user-data '$USER_DATA'"
    
    eval $DOCTL_CMD
    
    # Get droplet IP
    IP=$(doctl compute droplet list --format Name,PublicIPv4 --no-header | grep $DROPLET_NAME | awk '{print $2}')
    
    log_info "Droplet created!"
    log_info "IP Address: $IP"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Update OAuth redirect URIs with: http://$IP/api/auth/google/callback"
    log_info "  2. Edit .env on the droplet: docker compose exec app nano .env"
    log_info "  3. Access app at: http://$IP:8000"
}

# ===========================================
# STATUS CHECK
# ===========================================

check_status() {
    log_info "Checking deployment status..."
    
    # Check App Platform
    log_info "App Platform:"
    doctl apps list --format ID,Spec.Name,ActiveDeployment.CreatedAt --no-header 2>/dev/null || echo "  No apps found"
    
    echo ""
    
    # Check Droplets
    log_info "Droplets:"
    doctl compute droplet list --format Name,PublicIPv4,Status --no-header 2>/dev/null || echo "  No droplets found"
}

# ===========================================
# DESTROY
# ===========================================

destroy() {
    log_warn "This will destroy ALL maski deployments!"
    read -p "Type 'yes' to confirm: " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "Cancelled"
        exit 0
    fi
    
    # Destroy App Platform
    APP_ID=$(doctl apps list --format ID --no-header 2>/dev/null | grep -v "^$" | head -1)
    if [[ -n "$APP_ID" ]]; then
        log_info "Destroying App Platform app..."
        doctl apps delete $APP_ID --force
    fi
    
    # Destroy Droplets
    log_info "Destroying Droplets..."
    doctl compute droplet delete --force $(doctl compute droplet list --format ID --no-header | grep -v "^$") 2>/dev/null || true
    
    log_info "All resources destroyed"
}

# ===========================================
# MAIN
# ===========================================

main() {
    case "${1:-}" in
        app)
            check_doctl
            deploy_app_platform
            ;;
        droplet)
            check_doctl
            deploy_droplet
            ;;
        status)
            check_doctl
            check_status
            ;;
        destroy)
            check_doctl
            destroy
            ;;
        help|--help|-h)
            echo "maski AI Deployment Script"
            echo ""
            echo "Usage: ./deploy.sh <command>"
            echo ""
            echo "Commands:"
            echo "  app      Deploy to App Platform (requires managed DB)"
            echo "  droplet  Deploy to $4/mo Droplet with Docker"
            echo "  status   Check deployment status"
            echo "  destroy  Tear down all deployments"
            echo "  help     Show this help"
            echo ""
            echo "Prerequisites:"
            echo "  1. Install doctl: https://docs.digitalocean.com/reference/doctl/how-to/install/"
            echo "  2. Authenticate: doctl auth init"
            echo "  3. Set REPO variable in script to your GitHub repo"
            ;;
        *)
            log_error "Unknown command: $1"
            echo "Run: ./deploy.sh help"
            exit 1
            ;;
    esac
}

main "$@"
