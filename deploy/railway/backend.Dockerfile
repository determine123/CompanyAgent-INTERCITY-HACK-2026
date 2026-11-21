# Railway PRIVATE service named companyagent. No public Railway domain.
# It contains synthetic data only and deliberately has no real model/stock credentials.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    COMPANYAGENT_DEPLOYMENT_MODE=cloud_synthetic \
    COMPANYAGENT_RAILWAY_PRIVATE_BACKEND=true \
    COMPANYAGENT_COOKIE_SECURE=true \
    COMPANYAGENT_AUTO_SYNC=false \
    COMPANYAGENT_REAL_DATA_ENABLED=false \
    COMPANYAGENT_ALLOWED_DATA_HOSTS="" \
    COMPANYAGENT_RUNTIME_DIR=/app/runtime \
    HOST=0.0.0.0 PORT=8765
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .
RUN groupadd -g 10001 companyagent && \
    useradd -u 10001 -g 10001 -s /usr/sbin/nologin companyagent && \
    mkdir -p /app/runtime && chown -R 10001:10001 /app
USER 10001:10001
EXPOSE 8765
CMD ["python","server.py"]
