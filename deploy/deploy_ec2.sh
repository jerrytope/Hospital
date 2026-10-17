#!/usr/bin/env bash
# One-shot deploy for a fresh EC2 instance (Ubuntu or Amazon Linux). Safe to run again to update.
#
#   curl -fsSL https://raw.githubusercontent.com/jerrytope/Hospital/master/deploy/deploy_ec2.sh | bash
#
# Installs Docker, clones/updates the repo into /opt/hospital, writes .env on first run, builds and starts
# Postgres, Redis, the Django app, Celery and nginx (port 80), and on first run loads the demo content and
# creates an owner admin account. Served over plain HTTP on the instance's public IP until a domain is set up.
set -euo pipefail

# Wrapped in main() so bash reads the whole script before running any of it (safe with curl | bash).
main() {

REPO_URL="${REPO_URL:-https://github.com/jerrytope/Hospital.git}"
BRANCH="${BRANCH:-master}"
APP_DIR="${APP_DIR:-/opt/hospital}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.org}"

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"
log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

# --- Public IP (EC2 metadata, IMDSv2) -----------------------------------------------------------
TOKEN=$(curl -fsS -m 3 -X PUT http://169.254.169.254/latest/api/token \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)
PUBLIC_IP="${PUBLIC_IP:-$(curl -fsS -m 3 -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)}"
PUBLIC_IP="${PUBLIC_IP:-13.51.159.8}"
log "Deploying to http://$PUBLIC_IP"

# --- Packages and Docker ------------------------------------------------------------------------
if command -v apt-get >/dev/null; then
  log "Installing git and Docker (apt)"
  $SUDO apt-get update -y
  $SUDO apt-get install -y git curl openssl
  command -v docker >/dev/null || curl -fsSL https://get.docker.com | $SUDO sh
elif command -v dnf >/dev/null; then
  log "Installing git and Docker (dnf)"
  $SUDO dnf install -y git docker openssl
  ARCH=$(uname -m)
  PLUGINS=/usr/local/lib/docker/cli-plugins
  $SUDO mkdir -p "$PLUGINS"
  if ! $SUDO docker compose version >/dev/null 2>&1; then
    $SUDO curl -fsSL -o "$PLUGINS/docker-compose" \
      "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$ARCH"
    $SUDO chmod +x "$PLUGINS/docker-compose"
  fi
  if ! $SUDO docker buildx version >/dev/null 2>&1; then
    case "$ARCH" in x86_64) BX=amd64 ;; aarch64) BX=arm64 ;; *) BX=$ARCH ;; esac
    $SUDO curl -fsSL -o "$PLUGINS/docker-buildx" \
      "https://github.com/docker/buildx/releases/download/v0.19.3/buildx-v0.19.3.linux-$BX"
    $SUDO chmod +x "$PLUGINS/docker-buildx"
  fi
else
  echo "Unsupported OS: need apt-get or dnf." >&2
  exit 1
fi
$SUDO systemctl enable --now docker

# --- Swap (small instances run out of memory while building) ----------------------------------
MEM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$MEM_MB" -lt 3000 ] && ! $SUDO swapon --show | grep -q .; then
  log "Adding a 2 GB swap file (${MEM_MB} MB RAM)"
  $SUDO fallocate -l 2G /swapfile || $SUDO dd if=/dev/zero of=/swapfile bs=1M count=2048
  $SUDO chmod 600 /swapfile
  $SUDO mkswap /swapfile
  $SUDO swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
fi

# --- Code ---------------------------------------------------------------------------------------
if [ -d "$APP_DIR/.git" ]; then
  log "Updating code in $APP_DIR"
  $SUDO git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  $SUDO git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  log "Cloning $REPO_URL into $APP_DIR"
  $SUDO git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# --- .env (written once; later runs only refresh the IP so your own edits are kept) -------------
if [ ! -f .env ]; then
  log "Writing .env"
  $SUDO tee .env >/dev/null <<EOF
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=$(openssl rand -hex 32)
DEBUG=false
ALLOWED_HOSTS=$PUBLIC_IP,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://$PUBLIC_IP
SITE_URL=http://$PUBLIC_IP
TIME_ZONE=Africa/Lagos

# Plain HTTP until a domain and HTTPS are set up. Remove these four lines once HTTPS works.
SECURE_SSL_REDIRECT=false
SECURE_HSTS_SECONDS=0
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false

DATABASE_URL=postgres://hospital:hospital@db:5432/hospital
REDIS_URL=redis://redis:6379/0

ADMIN_PATH=admin
DJANGO_ADMIN_PATH=django-admin-fallback
ADMIN_REQUIRE_2FA=true

PAYSTACK_SECRET_KEY=
PAYSTACK_PUBLIC_KEY=
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

# Emails are printed to the container log until SMTP is set up. To send real email, delete
# EMAIL_BACKEND and fill in the Brevo SMTP details.
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=Haven Medical Relief <no-reply@example.org>

BREVO_API_KEY=
BREVO_LIST_ID=
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=
SENTRY_DSN=
EOF
  $SUDO chmod 600 .env
else
  log "Keeping existing .env (refreshing the IP)"
  $SUDO sed -i \
    -e "s#^ALLOWED_HOSTS=.*#ALLOWED_HOSTS=$PUBLIC_IP,localhost,127.0.0.1#" \
    -e "s#^CSRF_TRUSTED_ORIGINS=.*#CSRF_TRUSTED_ORIGINS=http://$PUBLIC_IP#" \
    -e "s#^SITE_URL=.*#SITE_URL=http://$PUBLIC_IP#" .env
fi

# --- Build, migrate, first-run setup, start -----------------------------------------------------
COMPOSE="$SUDO docker compose -f docker-compose.yml -f deploy/docker-compose.server.yml"

log "Building images (takes a few minutes the first time)"
$COMPOSE build

log "Starting database and Redis"
$COMPOSE up -d db redis

# The media volume starts out owned by root; the app runs as the 'app' user.
$COMPOSE run --rm -T --no-deps -u root web chown -R app:app /app/media

log "Running migrations"
$COMPOSE run --rm -T web python manage.py migrate --noinput

if [ ! -f .first-run-done ]; then
  log "First run: staff roles, demo content and owner account"
  $COMPOSE run --rm -T web python manage.py setup_roles
  $COMPOSE run --rm -T web python manage.py seed_demo
  ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
  $COMPOSE run --rm -T \
    -e DJANGO_SUPERUSER_EMAIL="$ADMIN_EMAIL" \
    -e DJANGO_SUPERUSER_PASSWORD="$ADMIN_PASSWORD" \
    -e DJANGO_SUPERUSER_FIRST_NAME=Site \
    -e DJANGO_SUPERUSER_LAST_NAME=Owner \
    web python manage.py createsuperuser --noinput
  printf 'Admin URL: http://%s/admin/\nEmail: %s\nPassword: %s\n' "$PUBLIC_IP" "$ADMIN_EMAIL" "$ADMIN_PASSWORD" \
    | $SUDO tee admin-credentials.txt >/dev/null
  $SUDO chmod 600 admin-credentials.txt
  $SUDO touch .first-run-done
fi

log "Starting all services"
$COMPOSE up -d --remove-orphans

# --- Check -----------------------------------------------------------------------------------
for _ in $(seq 1 30); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost/ || true)
  case "$CODE" in 200|301|302) break ;; esac
  sleep 2
done
$COMPOSE ps

echo
if [ -f admin-credentials.txt ]; then $SUDO cat admin-credentials.txt; fi
echo
echo "Site:  http://$PUBLIC_IP/   (local check returned HTTP ${CODE:-none})"
echo "Logs:  cd $APP_DIR && $COMPOSE logs -f web"
echo "Make sure the EC2 security group allows inbound TCP port 80."
}

main "$@" </dev/null
