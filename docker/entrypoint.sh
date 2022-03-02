#!/bin/sh
# Wait for PostGIS, apply migrations, optionally seed, then hand over to the
# container command. Every step is idempotent, so restarts are safe.
set -e

python3 - <<'PY'
import os
import socket
import sys
import time

host = os.getenv("POSTGRES_HOST", "db")
port = int(os.getenv("POSTGRES_PORT", "5432"))
deadline = time.time() + 60

while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print("database %s:%d is accepting connections" % (host, port))
            sys.exit(0)
    except OSError:
        time.sleep(1)

sys.exit("timed out waiting for %s:%d" % (host, port))
PY

echo "applying migrations ..."
python3 manage.py migrate --noinput

if [ "${SEED_DEMO:-true}" = "true" ]; then
    echo "seeding demo data ..."
    python3 manage.py seed_demo
fi

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "ensuring superuser ${DJANGO_SUPERUSER_USERNAME} exists ..."
    # Only skip creation when the user already exists; any other failure (a bad
    # email or a database error) should stop the container rather than vanish.
    if python3 manage.py shell --no-imports -c "import sys; from django.contrib.auth import get_user_model; sys.exit(get_user_model().objects.filter(username='${DJANGO_SUPERUSER_USERNAME}').exists())"; then
        python3 manage.py createsuperuser --noinput --username "${DJANGO_SUPERUSER_USERNAME}" \
            --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}"
    fi
fi

exec "$@"
