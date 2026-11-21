# Railway safety default: the repo-root image must NEVER expose raw FastAPI.
# This intentionally builds only the authenticated PUBLIC GATEWAY.
# Deploy the PRIVATE backend separately with deploy/railway/backend.Dockerfile.
# See deploy/railway/README.md for required auth and network configuration.
FROM caddy:2.10.2-alpine
COPY deploy/railway/Caddyfile /etc/caddy/Caddyfile
EXPOSE 8080
CMD ["caddy","run","--config","/etc/caddy/Caddyfile","--adapter","caddyfile"]
