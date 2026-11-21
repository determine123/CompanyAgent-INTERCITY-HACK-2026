# Ephemeral cloud-runner sandbox ONLY. Not a production deployment image.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 PORT=8765 \
    COMPANYAGENT_DEPLOYMENT_MODE=cloud_synthetic \
    COMPANYAGENT_AUTO_SYNC=false \
    COMPANYAGENT_ALLOWED_DATA_HOSTS="" \
    COMPANYAGENT_RUNTIME_DIR=/app/runtime
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .
RUN groupadd -g 10001 companyagent && \
    useradd -u 10001 -g 10001 -s /usr/sbin/nologin companyagent && \
    mkdir -p /app/runtime && chown -R 10001:10001 /app
USER 10001:10001
EXPOSE 8765
CMD ["python", "server.py"]
