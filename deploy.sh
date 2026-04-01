#!/usr/bin/env bash
set -euo pipefail

# maski AI - DigitalOcean App Platform Deployment

APP_NAME="maskai"
REPO="iklobato/app.maskai"

check_doctl() {
    if ! command -v doctl &> /dev/null; then
        echo "Error: doctl not installed"
        exit 1
    fi
    doctl account get &> /dev/null || { echo "Error: doctl not authenticated"; exit 1; }
}

get_app_id() {
    doctl apps list --format ID,Spec.Name --no-header 2>/dev/null | grep "maskai" | awk '{print $1}'
}

case "${1:-}" in
    create)
        check_doctl
        if [[ -n "$(get_app_id)" ]]; then
            echo "App already exists. Use 'update' to redeploy."
            exit 1
        fi
        if [[ ! -f "do/app.yaml" ]]; then
            echo "Error: do/app.yaml not found"
            exit 1
        fi
        doctl apps create --spec do/app.yaml
        ;;
    update)
        check_doctl
        APP_ID=$(get_app_id)
        [[ -z "$APP_ID" ]] && { echo "App not found. Run 'create' first."; exit 1; }
        doctl apps create-deployment "$APP_ID"
        ;;
    status)
        check_doctl
        APP_ID=$(get_app_id)
        [[ -z "$APP_ID" ]] && { echo "App not found."; exit 1; }
        doctl apps get "$APP_ID" --format "Name,LiveURL,Region"
        ;;
    url)
        check_doctl
        APP_ID=$(get_app_id)
        [[ -z "$APP_ID" ]] && { echo "App not found."; exit 1; }
        doctl apps get "$APP_ID" --format "LiveURL" | tail -1 | tr -d ' '
        ;;
    destroy)
        check_doctl
        APP_ID=$(get_app_id)
        [[ -z "$APP_ID" ]] && { echo "App not found."; exit 1; }
        read -p "Destroy app? (yes/no): " confirm
        [[ "$confirm" == "yes" ]] && doctl apps delete "$APP_ID" --force
        ;;
    *)
        echo "Usage: ./deploy.sh {create|update|status|url|destroy}"
        ;;
esac
