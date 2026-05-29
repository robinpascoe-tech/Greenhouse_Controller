#!/usr/bin/env bash
#
# Deploy the legacy PHP dashboard to the local web root.
#
# This script is intended to run on the Raspberry Pi from the repository root:
#
#   cd /home/pi/Greenhouse_Controller
#   tools/deploy_dashboard.sh
#
# It copies html/ into /var/www/html while preserving dbconnect.local.php, which
# contains live database credentials and must not be tracked by Git.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SOURCE_DIR="${SOURCE_DIR:-$REPO_ROOT/html}"
WEB_ROOT="${WEB_ROOT:-/var/www/html}"
WEB_USER="${WEB_USER:-www-data}"
WEB_GROUP="${WEB_GROUP:-www-data}"
LOCAL_CONFIG="$WEB_ROOT/dbconnect.local.php"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/dashboard_deploy_backups}"
STAMP="$(date -u +%Y%m%d-%H%M%SZ)"
BACKUP_FILE="$BACKUP_DIR/dashboard_before_$STAMP.tar.gz"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Dashboard source directory not found: $SOURCE_DIR" >&2
  exit 1
fi

if [[ ! -d "$WEB_ROOT" ]]; then
  echo "Web root not found: $WEB_ROOT" >&2
  exit 1
fi

if [[ ! -f "$LOCAL_CONFIG" ]]; then
  cat >&2 <<EOF
Missing local dashboard database config:
  $LOCAL_CONFIG

Create it before deploying so live database credentials are not overwritten.
See docs/INSTALL.md for the expected dbconnect.local.php format.
EOF
  exit 1
fi

echo "Backing up current dashboard to $BACKUP_FILE"
mkdir -p "$BACKUP_DIR"
sudo tar -czf "$BACKUP_FILE" -C "$WEB_ROOT" .

TMP_CONFIG="$(sudo mktemp)"
sudo cp "$LOCAL_CONFIG" "$TMP_CONFIG"

echo "Copying dashboard files from $SOURCE_DIR to $WEB_ROOT"
sudo rsync -a --delete \
  --exclude 'dbconnect.local.php' \
  "$SOURCE_DIR"/ "$WEB_ROOT"/

sudo cp "$TMP_CONFIG" "$LOCAL_CONFIG"
sudo rm -f "$TMP_CONFIG"

sudo chown -R "$WEB_USER:$WEB_GROUP" "$WEB_ROOT"
sudo chmod 640 "$LOCAL_CONFIG"

echo "Checking PHP syntax"
if command -v php >/dev/null 2>&1; then
  php -l "$WEB_ROOT/dbconnect.php" >/dev/null
  php -l "$WEB_ROOT/gettemps.php" >/dev/null
  php -l "$WEB_ROOT/gettempsall.php" >/dev/null
  php -l "$WEB_ROOT/indexcontent.php" >/dev/null
else
  echo "php command not found; skipping syntax checks" >&2
fi

echo "Checking dashboard endpoints"
if command -v curl >/dev/null 2>&1; then
  for endpoint in gettemps.php gettempsall.php indexcontent.php; do
    status="$(curl -sS -o /dev/null -w '%{http_code}' "http://localhost/$endpoint")"
    if [[ "$status" != "200" ]]; then
      echo "Endpoint check failed for $endpoint: HTTP $status" >&2
      exit 1
    fi
    echo "  $endpoint: HTTP $status"
  done
else
  echo "curl command not found; skipping endpoint checks" >&2
fi

echo "Dashboard deployment complete."
