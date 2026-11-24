#!/bin/sh
# Write runtime config for the browser from container env vars.
set -eu
cat > /usr/share/nginx/html/env.js <<JS
window.__APP_CONFIG__ = { API_URL: "${API_URL:-http://localhost:8000}", USER_NAME: "${USER_NAME:-}" };
JS
echo "env.js written (API_URL=${API_URL:-http://localhost:8000})"
