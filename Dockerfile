# syntax=docker/dockerfile:1

############################
# Build stage: wheels only #
############################
FROM python:3.10-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /wheels
COPY requirements.txt .
# Resolve and download every dependency here so the runtime stage never needs
# pip's build tooling or a network connection.
RUN pip wheel --wheel-dir /wheels -r requirements.txt


##################################
# Runtime stage: libraries only  #
##################################
FROM python:3.10-slim-bookworm AS runtime

# GeoDjango loads these through ctypes at import time. The -dev packages are
# deliberately absent: only the shared objects are needed at runtime.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libgdal32 \
        libgeos-c1v5 \
        libproj25 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=testproject.settings \
    DJANGO_STATIC_ROOT=/app/staticfiles

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
        -r /wheels/requirements.txt \
    && rm -rf /wheels

COPY manage.py ./
COPY testproject ./testproject
COPY testapp ./testapp
COPY examples ./examples
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && adduser --system --group --no-create-home app \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/testapp/provider/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["entrypoint.sh"]
CMD ["gunicorn", "testproject.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--timeout", "30", "--access-logfile", "-"]
