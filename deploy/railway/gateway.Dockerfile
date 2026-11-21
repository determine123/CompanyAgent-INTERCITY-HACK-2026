# Railway PUBLIC service named companyagent-gateway.
# Railway terminates HTTPS and forwards to HTTP port 8080; Caddy applies Basic Auth.
FROM caddy:2.10.2-alpine
COPY deploy/railway/Caddyfile /etc/caddy/Caddyfile
EXPOSE 8080
CMD ["caddy","run","--config","/etc/caddy/Caddyfile","--adapter","caddyfile"]
