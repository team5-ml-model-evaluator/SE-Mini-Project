# MLE-3: HTTPS and TLS security configuration

## Django application settings

`config/settings.py` keeps HTTP usable for local development (`DJANGO_DEBUG=1`).
When `DJANGO_DEBUG=0`, HTTPS redirects and secure session/CSRF cookies default to
enabled. Their values can be explicitly set with `SECURE_SSL_REDIRECT`,
`SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE`; use `0`/`1`, `false`/`true`,
`no`/`yes`, or `off`/`on`. Invalid boolean values fail during settings loading.

The existing `Lax` SameSite policy, HTTP-only session cookie, and `X_FRAME_OPTIONS =
"DENY"` are preserved. Django also enables content-type sniffing protection and
uses the `strict-origin-when-cross-origin` referrer policy.

Set `CSRF_TRUSTED_ORIGINS` to a comma-separated list of explicit origins, including
their scheme (for example, `https://evaluator.example.org`). `DJANGO_ALLOWED_HOSTS`
continues to define the allowed hostnames. In production, set `DJANGO_DEBUG=0`,
provide a strong `DJANGO_SECRET_KEY` through the deployment's secret manager, and
configure the production hostnames and CSRF origins.

## TLS termination and reverse proxies

There is no Nginx, Apache, container, or hosting-platform configuration in this
repository, and no deployed HTTPS endpoint is available here for live verification.
Django does not negotiate TLS and cannot enforce the minimum TLS protocol. Configure
the public web server, load balancer, or hosting platform to accept TLS 1.2 and TLS
1.3 only, terminate HTTPS with a valid deployment-managed certificate, and redirect
HTTP to HTTPS. Do not permit TLS 1.0 or 1.1.

For Nginx, the relevant directives belong in the deployment-managed HTTPS virtual
host (certificate paths below are placeholders, not application secrets):

```nginx
server {
    listen 80;
    server_name evaluator.example.org;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name evaluator.example.org;

    ssl_certificate /path/from/deployment/certificate.pem;
    ssl_certificate_key /path/from/deployment/private-key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Only when the application is reachable exclusively through a trusted proxy that
overwrites `X-Forwarded-Proto`, set `TRUST_X_FORWARDED_PROTO=1`. This configures
Django to trust exactly `HTTP_X_FORWARDED_PROTO: https` for determining whether a
request is secure. Do not enable it for direct-to-application deployments or if the
proxy forwards client-supplied values unchanged. Restrict network access to the
application so clients cannot bypass the trusted proxy.

## HSTS

HSTS is disabled by default (`SECURE_HSTS_SECONDS=0`) and remains disabled for local
development. After HTTPS and HTTP redirects have been deployed and verified for
every production hostname, enable it with, for example,
`SECURE_HSTS_SECONDS=31536000`. Set `SECURE_HSTS_INCLUDE_SUBDOMAINS=1` only if every
subdomain supports HTTPS. Preload is not enabled. HSTS can make a misconfigured
domain inaccessible in browsers until its policy expires, so enable it deliberately.

## Production environment example

Supply secrets using the hosting provider's secret manager; do not commit them:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<deployment-managed-secret>
DJANGO_ALLOWED_HOSTS=evaluator.example.org
CSRF_TRUSTED_ORIGINS=https://evaluator.example.org
SECURE_SSL_REDIRECT=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=0
TRUST_X_FORWARDED_PROTO=1
```

Omit `TRUST_X_FORWARDED_PROTO` unless the deployment meets the trusted-proxy
requirements above. Omit or leave HSTS at `0` until HTTPS is operational.

## Verification

After deployment, verify the HTTP endpoint redirects and valid TLS works:

```text
curl -I http://evaluator.example.org/
curl --tlsv1.2 --tls-max 1.2 -I https://evaluator.example.org/
curl --tlsv1.3 --tls-max 1.3 -I https://evaluator.example.org/
```

Also test that a TLS 1.1 handshake fails using the TLS client available in the
deployment environment, and inspect the certificate chain with normal certificate
verification enabled. Record the deployment host, date, and command output as the
evidence for MLE-SR-001. No live verification can be claimed until an HTTPS endpoint
is provisioned.
