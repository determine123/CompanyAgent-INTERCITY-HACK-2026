# Railway PUBLIC SYNTHETIC DEMO only. No enterprise data or external API credentials.
# HTTPS terminates at Railway. Internal Caddy enforces authentication on $PORT.
# FastAPI is bound to loopback :8765 and is never directly published.
FROM caddy:2.10.2-alpine AS caddy_bin
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COMPANYAGENT_DEPLOYMENT_MODE=cloud_synthetic \
    COMPANYAGENT_AUTO_SYNC=false \
    COMPANYAGENT_REAL_DATA_ENABLED=false \
    COMPANYAGENT_ALLOWED_DATA_HOSTS="" \
    COMPANYAGENT_COOKIE_SECURE=true \
    COMPANYAGENT_RUNTIME_DIR=/app/runtime \
    PORT=8080
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY --from=caddy_bin /usr/bin/caddy /usr/local/bin/caddy
COPY . .
RUN groupadd -g 10001 companyagent \
 && useradd -u 10001 -g 10001 -s /usr/sbin/nologin companyagent \
 && mkdir -p /app/runtime \
 && chown -R 10001:10001 /app
USER 10001:10001
EXPOSE 8080
CMD ["python","deploy/railway/start.py"]
