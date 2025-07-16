# Reverse Proxy Configuration

StreamVault automatically detects when it's running behind a reverse proxy and adjusts security settings accordingly.

## Automatic Detection

StreamVault looks for these headers to detect reverse proxy setups:

- `X-Forwarded-Proto`
- `X-Forwarded-SSL`
- `X-Forwarded-Host`
- `X-Real-IP`
- `X-Forwarded-For`
- `CF-Connecting-IP` (Cloudflare)
- `X-Original-Forwarded-For` (AWS ALB)

## Cookie Security

### Automatic Configuration

When behind a reverse proxy:
- **HTTPS detected**: Secure cookies are enabled
- **HTTP only**: Secure cookies are disabled (with warning)

### Manual Override

Set the environment variable to override auto-detection:

```bash
# Force secure cookies on (even if not detected)
USE_SECURE_COOKIES=true

# Force secure cookies off (for development)
USE_SECURE_COOKIES=false
```

## Common Reverse Proxy Configurations

### Nginx

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://streamvault:7000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-SSL on;
    }
}
```

### Traefik

```yaml
# docker-compose.yml
services:
  streamvault:
    labels:
      - "traefik.http.routers.streamvault.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.streamvault.tls=true"
      - "traefik.http.services.streamvault.loadbalancer.server.port=7000"
```

### Apache

```apache
<VirtualHost *:443>
    ServerName your-domain.com
    
    ProxyPass / http://streamvault:7000/
    ProxyPassReverse / http://streamvault:7000/
    
    ProxyPreserveHost On
    ProxyAddHeaders On
    
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-SSL "on"
</VirtualHost>
```

### Cloudflare

When using Cloudflare, the following headers are automatically set:
- `CF-Connecting-IP`
- `X-Forwarded-Proto`

No additional configuration needed.

## Security Considerations

1. **Always use HTTPS** in production with reverse proxies
2. **Verify headers** are being set correctly by your proxy
3. **Monitor logs** for security warnings about insecure cookies
4. **Test cookie behavior** after proxy configuration changes

## Debugging

Check the application logs for cookie security configuration:

```
🔒 Detected HTTPS reverse proxy - enabling secure cookies
🍪 Secure cookies: Yes
```

Or for HTTP-only setups:

```
⚠️ Detected reverse proxy without HTTPS - disabling secure cookies
⚠️ For production, ensure your reverse proxy terminates SSL/TLS
🍪 Secure cookies: No
```
