# syntax=docker/dockerfile:1

############################################
# Build stage: resolve Python dependencies #
############################################
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
# Installed into a plain directory rather than a venv: the runtime image has
# its own Python 3.12 and only needs the packages on PYTHONPATH.
RUN pip install --target /opt/site -r requirements.txt


################################################
# Runtime stage: GDAL, GEOS and PROJ prebuilt  #
################################################
# OSGeo's image ships the shared libraries GeoDjango loads through ctypes,
# for both amd64 and arm64, so nothing has to be compiled or apt-installed.
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.12.0 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/site \
    DJANGO_SETTINGS_MODULE=testproject.settings \
    DJANGO_STATIC_ROOT=/app/staticfiles

WORKDIR /app

COPY --from=builder /opt/site /opt/site
COPY manage.py ./
COPY testproject ./testproject
COPY testapp ./testapp
COPY examples ./examples
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && DJANGO_SECRET_KEY=build-only python3 manage.py collectstatic --noinput \
    && useradd --system --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD python3 -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/testapp/provider/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["entrypoint.sh"]
CMD ["python3", "-m", "gunicorn", "testproject.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--timeout", "30", "--access-logfile", "-"]
