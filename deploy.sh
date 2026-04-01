#!/usr/bin/env bash
set -euo pipefail

# ===========================================
# maski AI - DigitalOcean App Platform Deployment
# ===========================================
#
# Usage:
#   ./deploy.sh create    # Create new App
#   ./deploy.sh update    # Update existing App
#   ./deploy.sh logs      # View deployment logs
#   ./deploy.sh status    # Check app status
#   ./deploy.sh destroy   # Tear down the app
# ===========================================

# Configuration
REGION="nyc"
APP_NAME="maskai"
REPO="iklobato/app.maskai"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Check if doctl is installed
check_doctl() {
    if ! command -v doctl &> /dev/null; then
        log_error "doctl is not installed"
        echo "Install: brew install doctl"
        exit 1
    fi
    
    if ! doctl account get &> /dev/null; then
        log_error "doctl not authenticated. Run: doctl auth init"
        exit 1
    fi
    
    log_info "doctl ready"
}

# Generate app spec YAML
create_app_spec() {
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
      repo: iklobato/app.maskai
    http_port: 8000
    instance_count: 1
    instance_size_slug: basic-xxs
    name: web
    run_command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
EOF
}

# Create new App
create_app() {
    log_step "Creating DigitalOcean App Platform deployment..."
    
    # Check if app already exists
    if doctl apps list --format Name --no-header 2>/dev/null | grep -q "^maskai$"; then
        log_warn "App 'maskai' already exists. Use './deploy.sh update' to redeploy."
        exit 1
    fi
    
    create_app_spec
    
    log_info "Creating app..."
    APP_OUTPUT=$(doctl apps create --spec /tmp/maskai-app.yaml 2>&1)
    APP_ID=$(echo "$APP_OUTPUT" | grep -oP '(?<=id\s{10})\S+' | head -1 || echo "$APP_OUTPUT" | grep -oP '\b[0-9a-f-]{36}\b' | head -1)
    
    if [[ -z "$APP_ID" ]]; then
        log_error "Failed to create app. Check doctl output."
        echo "$APP_OUTPUT"
        exit 1
    fi
    
    log_info "App created with ID: $APP_ID"
    rm /tmp/maskai-app.yaml
    
    echo ""
    log_info "=============================================="
    log_info "App Platform deployment initiated!"
    log_info "=============================================="
    echo ""
    log_step "Next steps:"
    echo ""
    echo "1. Wait 5-10 minutes for initial deployment"
    echo ""
    echo "2. Get your app URL:"
    echo "   doctl apps get $APP_ID"
    echo ""
    echo "3. Add these environment variables in the dashboard:"
    echo "   https://cloud.digitalocean.com/apps"
    echo ""
    echo "   Required variables:"
    echo "   - JWT_SECRET_KEY (generate: openssl rand -hex 32)"
    echo "   - ENCRYPTION_KEY (generate: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
    echo "   - GOOGLE_CLIENT_ID"
    echo "   - GOOGLE_CLIENT_SECRET"
    echo "   - GOOGLE_REDIRECT_URI (https://your-app.ondigitalocean.app/api/auth/google/callback)"
    echo "   - MICROSOFT_CLIENT_ID"
    echo "   - MICROSOFT_CLIENT_SECRET"
    echo "   - MICROSOFT_REDIRECT_URI (https://your-app.ondigitalocean.app/api/auth/microsoft/callback)"
    echo "   - STRIPE_SECRET_KEY"
    echo "   - STRIPE_WEBHOOK_SECRET"
    echo "   - STRIPE_PRICE_BASIC"
    echo "   - STRIPE_PRICE_PRO"
    echo "   - STRIPE_PRICE_ENTERPRISE"
    echo "   - APP_URL (https://your-app.ondigitalocean.app)"
    echo "   - ENV (production)"
    echo ""
    echo "4. Configure OAuth redirect URIs in Google/Azure with your app URL"
    echo ""
    echo "5. Trigger redeploy after adding env vars:"
    echo "   ./deploy.sh update"
}

# Update/Redeploy existing app
update_app() {
    log_step "Updating/redeploying app..."
    
    APP_ID=$(doctl apps list --format ID,Spec.Name --no-header 2>/dev/null | grep "maskai" | awk '{print $1}')
    
    if [[ -z "$APP_ID" ]]; then
        log_error "App 'maskai' not found. Run './deploy.sh create' first."
        exit 1
    fi
    
    log_info "Triggering deployment for app: $APP_ID"
    doctl apps create-deployment "$APP_ID"
    
    log_info "Deployment triggered. Check status with:"
    echo "  ./deploy.sh status"
}

# View logs
view_logs() {
    APP_ID=$(doctl apps list --format ID,Spec.Name --no-header 2>/dev/null | grep "maskai" | awk '{print $1}')
    
    if [[ -z "$APP_ID" ]]; then
        log_error "App 'maskai' not found."
        exit 1
    fi
    
    log_info "Recent logs:"
    doctl apps logs "$APP_ID" --deployment latest --follow 2>/dev/null || \
    doctl apps get "$APP_ID"
}

# Check status
check_status() {
    APP_ID=$(doctl apps list --format ID,Spec.Name --no-header 2>/dev/null | grep "maskai" | awk '{print $1}')
    
    if [[ -z "$APP_ID" ]]; then
        log_error "App 'maskai' not found. Run './deploy.sh create' first."
        exit 1
    fi
    
    log_info "App Status:"
    doctl apps get "$APP_ID" --format "ID,Spec.Name,LiveURL,LastDeploymentCreatedAt,Region" 2>/dev/null || \
    doctl apps list
    
    echo ""
    log_info "Recent deployments:"
    doctl apps list-deployments "$APP_ID" --format "ID,Phase,CreatedAt" 2>/dev/null || true
}

# Get app URL
get_url() {
    APP_ID=$(doctl apps list --format ID,Spec.Name --no-header 2>/dev/null | grep "maskai" | awk '{print $1}')
    
    if [[ -z "$APP_ID" ]]; then
        log_error "App 'maskai' not found."
        exit 1
    fi
    
    URL=$(doctl apps get "$APP_ID" --format "LiveURL" 2>/dev/null | grep -v "LiveURL" | tr -d ' ')
    
    if [[ -n "$URL" ]]; then
        echo "$URL"
    else
        log_warn "App not live yet. Check deployment status."
    fi
}

# Destroy app
destroy_app() {
    APP_ID=$(doctl apps list --format ID,Spec.Name --no-header 2>/dev/null | grep "maskai" | awk '{print $1}')
    
    if [[ -z "$APP_ID" ]]; then
        log_error "App 'maskai' not found."
        exit 1
    fi
    
    log_warn "This will DESTROY the app and ALL associated resources!"
    log_warn "This action cannot be undone."
    echo ""
    read -p "Type 'yes' to confirm: " confirm
    
    if [[ "$confirm" != "yes" ]]; then
        log_info "Cancelled."
        exit 0
    fi
    
    log_info "Destroying app: $APP_ID"
    doctl apps delete "$APP_ID" --force
    log_info "App destroyed."
}

# Help
show_help() {
    cat << 'EOF'
maski AI - DigitalOcean App Platform Deployment

Usage:
  ./deploy.sh <command>

Commands:
  create    Create new App Platform deployment
  update    Redeploy/trigger new deployment
  logs      View deployment logs
  status    Check app status and deployments
  url       Get the app's live URL
  destroy   Tear down the app and all resources
  help      Show this help

Prerequisites:
  1. Install doctl:
     brew install doctl
  
  2. Authenticate:
     doctl auth init
  
  3. Connect GitHub repo:
     doctl apps update --github-repo iklobato/app.maskai --github-branch main

First deployment:
  ./deploy.sh create

Check status:
  ./deploy.sh status
  ./deploy.sh url

Redeploy after changes:
  ./deploy.sh update
EOF
}

# Main
main() {
    check_doctl
    
    case "${1:-}" in
        create)
            create_app
            ;;
        update)
            update_app
            ;;
        logs)
            view_logs
            ;;
        status)
            check_status
            ;;
        url)
            get_url
            ;;
        destroy)
            destroy_app
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
