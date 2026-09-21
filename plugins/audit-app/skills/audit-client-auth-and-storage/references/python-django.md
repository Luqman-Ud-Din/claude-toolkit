# Python / Django (DRF, Flask, FastAPI) reference for audit-client-auth-and-storage

Client auth is a frontend topic; this file covers what the Python API
contributes to the client's flow - token issuance shape and lifetime, refresh
and logout endpoints, and what the server hands the client. Validation and
role enforcement belong to `audit-authz-and-access-control`; cookie flags, CORS
and headers to `audit-security-headers-and-middleware`.

## Stack markers
`requirements.txt`/`pyproject.toml` with `djangorestframework`, `djangorestframework-simplejwt`, `dj-rest-auth`, `django-allauth`, `django-cors-headers`, `flask-jwt-extended`, `flask-login`, `fastapi` + `python-jose`/`pyjwt`/`fastapi-users`/`authlib`.

## Where the relevant code lives
`settings.py` (`SIMPLE_JWT = {...}`, `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`, `SESSION_COOKIE_*`, `CSRF_*`, `CORS_ALLOW_CREDENTIALS`, `CORS_ALLOWED_ORIGINS`), `urls.py` (`TokenObtainPairView`, `TokenRefreshView`, `TokenBlacklistView`, `dj_rest_auth.urls`), `**/auth/views.py`, `**/authentication.py` (custom `BaseAuthentication` reading cookies/query), Flask `app.py` (`JWTManager`, `JWT_TOKEN_LOCATION`, `JWT_COOKIE_*`), FastAPI `auth.py` (`OAuth2PasswordBearer`, `jwt.encode(... exp ...)`, `Response.set_cookie`), `channels` consumers (token in query string).

## What this skill checks on the server side
- **Issuance shape**: DRF SimpleJWT returns `{"access","refresh"}` in the body (client must store); `dj-rest-auth` `JWT_AUTH_COOKIE`/`JWT_AUTH_REFRESH_COOKIE` with `JWT_AUTH_HTTPONLY = True` moves them to HttpOnly cookies; Django session auth (`sessionid`) is HttpOnly by default; Flask-JWT-Extended `JWT_TOKEN_LOCATION = ["cookies"]` with `JWT_COOKIE_CSRF_PROTECT`; FastAPI `response.set_cookie(httponly=True, secure=True, samesite="strict")`.
- **Lifetimes**: `SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(days=30)` (should be minutes), `REFRESH_TOKEN_LIFETIME`, `ROTATE_REFRESH_TOKENS`, `BLACKLIST_AFTER_ROTATION`; `jwt.encode` without `exp`; `JWT_ACCESS_TOKEN_EXPIRES = False` (Flask); `SESSION_COOKIE_AGE` very long with `SESSION_SAVE_EVERY_REQUEST = False`.
- **Refresh**: `TokenRefreshView` routed; rotation + blacklist app (`rest_framework_simplejwt.token_blacklist` in `INSTALLED_APPS`); refresh from body vs HttpOnly cookie.
- **Logout / revocation**: `TokenBlacklistView` or `dj_rest_auth` logout (`LOGOUT_ON_PASSWORD_CHANGE`), `django.contrib.auth.logout` for sessions, Flask `unset_jwt_cookies`, FastAPI cookie deletion + refresh row delete.
- **Where the token is read**: custom authentication classes reading `request.GET.get("token")` or cookies; Channels `AuthMiddlewareStack` with query-string tokens.
- **Public identifiers vs secrets**: `/api/config/` views returning `settings.*` values; templates injecting `settings.SECRET`-like values into `window.__CONFIG__` via `json_script`.
- **CORS**: `CORS_ALLOW_ALL_ORIGINS = True` with `CORS_ALLOW_CREDENTIALS = True` - headers skill; cite here if cookies are used.

## What "good" looks like
```python
# settings.py
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
INSTALLED_APPS += ["rest_framework_simplejwt.token_blacklist"]
REST_AUTH = {"USE_JWT": True, "JWT_AUTH_COOKIE": "access", "JWT_AUTH_REFRESH_COOKIE": "refresh",
             "JWT_AUTH_HTTPONLY": True, "JWT_AUTH_SECURE": True, "JWT_AUTH_SAMESITE": "Strict"}
```
```python
# FastAPI
access = jwt.encode({"sub": user.id, "exp": now + timedelta(minutes=15)}, settings.jwt_key, algorithm="HS256")
response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="strict", path="/auth/refresh", max_age=14*86400)
return {"access_token": access, "expires_in": 900}
```

## Manual trace checklist
1. Token views routed (`urls.py`) and response shape; cookie settings in `REST_AUTH`/Flask config.
2. `SIMPLE_JWT` lifetimes and rotation/blacklist; `jwt.encode` `exp` presence.
3. Refresh view/rotation and blacklist app installed.
4. Logout view revoking refresh tokens / unsetting cookies; `logout()` for sessions.
5. Config views or templates leaking settings to the client.
6. Channels/WebSocket token transport; not logged.

## Stack-specific false positives
- SimpleJWT body tokens with 5-15 minute access TTL and rotation - acceptable when the client keeps access in memory (client finding decides).
- Django session auth with `SESSION_COOKIE_HTTPONLY = True` (default) - the HttpOnly path; CSRF handled by Django middleware.
- `OAuth2PasswordBearer` extracting from the `Authorization` header - normal.

## Tooling
- `grep -rn "TOKEN_LIFETIME\|expires\|exp\b\|set_cookie\|JWT_TOKEN_LOCATION" --include=*.py`.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/python-django.json`.

## References
djangorestframework-simplejwt settings docs; dj-rest-auth JWT cookie docs; Flask-JWT-Extended "JWT in cookies"; FastAPI security tutorial; OWASP Session Management and JWT cheat sheets. CWE-613, CWE-522, CWE-384; ASVS 3.2-3.5; OWASP A07:2021. Sibling skills: `audit-authz-and-access-control`, `audit-security-headers-and-middleware`, `audit-secrets-and-config`.
