import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientSession, ClientTimeout, web


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""


UPSTREAM_BASE_URL = env("UPSTREAM_BASE_URL", "http://srv-captain--trvl:8080").rstrip("/")
UPSTREAM_BEARER_TOKEN = env("UPSTREAM_BEARER_TOKEN", required=True)
OAUTH_USERNAME = env("OAUTH_USERNAME", required=True)
OAUTH_PASSWORD = env("OAUTH_PASSWORD", required=True)
OAUTH_CLIENT_ID = env("OAUTH_CLIENT_ID", "trvl-chatgpt")
OAUTH_CLIENT_SECRET = env("OAUTH_CLIENT_SECRET", required=True)
TOKEN_TTL = int(env("OAUTH_ACCESS_TOKEN_TTL_SECONDS", "3600"))
REFRESH_TTL = int(env("OAUTH_REFRESH_TOKEN_TTL_SECONDS", "2592000"))
CODE_TTL = int(env("OAUTH_CODE_TTL_SECONDS", "300"))
SCOPE = env("OAUTH_SCOPE", "trvl")
ALLOWED_REDIRECT_PREFIXES = [
    prefix.strip()
    for prefix in env(
        "OAUTH_ALLOWED_REDIRECT_PREFIXES",
        "https://chatgpt.com/,https://chat.openai.com/,http://127.0.0.1,http://localhost",
    ).split(",")
    if prefix.strip()
]

auth_codes: dict[str, dict[str, Any]] = {}
access_tokens: dict[str, dict[str, Any]] = {}
refresh_tokens: dict[str, dict[str, Any]] = {}


def now() -> int:
    return int(time.time())


def base_url(request: web.Request) -> str:
    configured = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme).split(",")[0].strip()
    host = request.headers.get("X-Forwarded-Host", request.host).split(",")[0].strip()
    return f"{scheme}://{host}"


def safe_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


def client_auth_ok(request: web.Request, data: dict[str, str]) -> bool:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth.split(" ", 1)[1]).decode()
            client_id, client_secret = decoded.split(":", 1)
            return safe_equal(client_id, OAUTH_CLIENT_ID) and safe_equal(client_secret, OAUTH_CLIENT_SECRET)
        except Exception:
            return False

    return safe_equal(data.get("client_id", ""), OAUTH_CLIENT_ID) and safe_equal(
        data.get("client_secret", ""), OAUTH_CLIENT_SECRET
    )


def redirect_allowed(redirect_uri: str) -> bool:
    return any(redirect_uri.startswith(prefix) for prefix in ALLOWED_REDIRECT_PREFIXES)


def cleanup_expired() -> None:
    current = now()
    for store in (auth_codes, access_tokens, refresh_tokens):
        expired = [key for key, value in store.items() if value["expires_at"] <= current]
        for key in expired:
            store.pop(key, None)


def pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def json_response(payload: dict[str, Any], status: int = 200, headers: dict[str, str] | None = None) -> web.Response:
    response = web.json_response(payload, status=status, headers=headers)
    response.headers["Cache-Control"] = "no-store"
    return response


def cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, MCP-Protocol-Version",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }


async def health(request: web.Request) -> web.Response:
    return json_response(
        {
            "status": "ok",
            "server": "trvl-oauth-bridge",
            "upstream": UPSTREAM_BASE_URL,
            "oauth": {
                "issuer": base_url(request),
                "client_id": OAUTH_CLIENT_ID,
                "scope": SCOPE,
            },
        }
    )


async def protected_resource_metadata(request: web.Request) -> web.Response:
    root = base_url(request)
    return json_response(
        {
            "resource": f"{root}/mcp",
            "authorization_servers": [root],
            "bearer_methods_supported": ["header"],
            "scopes_supported": [SCOPE],
            "resource_documentation": "https://github.com/TylonHH/trvl-caprover",
        }
    )


async def authorization_server_metadata(request: web.Request) -> web.Response:
    root = base_url(request)
    return json_response(
        {
            "issuer": root,
            "authorization_endpoint": f"{root}/authorize",
            "token_endpoint": f"{root}/token",
            "introspection_endpoint": f"{root}/introspect",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
            "scopes_supported": [SCOPE],
            "authorization_response_iss_parameter_supported": True,
        }
    )


def validate_authorize_params(params: dict[str, str]) -> str | None:
    if params.get("response_type") != "code":
        return "response_type must be code"
    if params.get("client_id") != OAUTH_CLIENT_ID:
        return "invalid client_id"
    if not params.get("redirect_uri") or not redirect_allowed(params["redirect_uri"]):
        return "redirect_uri is not allowed"
    if params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
        return "PKCE S256 is required"
    return None


def login_page(request: web.Request, error: str | None = None) -> web.Response:
    message = f"<p class='error'>{html.escape(error)}</p>" if error else ""
    action = html.escape(str(request.rel_url))
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sign in to trvl</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 34rem; }}
    label {{ display: block; margin-top: 1rem; }}
    input {{ box-sizing: border-box; font: inherit; padding: .55rem; width: 100%; }}
    button {{ font: inherit; margin-top: 1.25rem; padding: .65rem 1rem; }}
    .error {{ color: #b00020; }}
  </style>
</head>
<body>
  <h1>Sign in to trvl</h1>
  <p>Use the OAuth username and password configured in CapRover.</p>
  {message}
  <form method="post" action="{action}">
    <label>Username <input name="username" autocomplete="username" required></label>
    <label>Password <input name="password" type="password" autocomplete="current-password" required></label>
    <button type="submit">Authorize ChatGPT</button>
  </form>
</body>
</html>"""
    return web.Response(text=body, content_type="text/html")


async def authorize_get(request: web.Request) -> web.Response:
    params = {key: request.query.get(key, "") for key in request.query}
    error = validate_authorize_params(params)
    if error:
        return web.Response(text=error, status=400)
    return login_page(request)


async def authorize_post(request: web.Request) -> web.Response:
    params = {key: request.query.get(key, "") for key in request.query}
    error = validate_authorize_params(params)
    if error:
        return web.Response(text=error, status=400)

    form = await request.post()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    if not (safe_equal(username, OAUTH_USERNAME) and safe_equal(password, OAUTH_PASSWORD)):
        return login_page(request, "Invalid username or password.")

    cleanup_expired()
    code = secrets.token_urlsafe(32)
    auth_codes[code] = {
        "client_id": params["client_id"],
        "redirect_uri": params["redirect_uri"],
        "code_challenge": params["code_challenge"],
        "scope": params.get("scope") or SCOPE,
        "resource": params.get("resource") or f"{base_url(request)}/mcp",
        "expires_at": now() + CODE_TTL,
    }

    redirect_params = {"code": code, "iss": base_url(request)}
    if params.get("state"):
        redirect_params["state"] = params["state"]
    separator = "&" if "?" in params["redirect_uri"] else "?"
    raise web.HTTPFound(location=f"{params['redirect_uri']}{separator}{urlencode(redirect_params)}")


async def parse_token_request(request: web.Request) -> dict[str, str]:
    if request.content_type == "application/json":
        payload = await request.json()
        return {str(key): str(value) for key, value in payload.items()}
    form = await request.post()
    return {str(key): str(value) for key, value in form.items()}


def issue_tokens(scope: str, resource: str) -> dict[str, Any]:
    current = now()
    access_token = secrets.token_urlsafe(48)
    refresh_token = secrets.token_urlsafe(48)
    token_record = {
        "scope": scope,
        "resource": resource,
        "issued_at": current,
        "expires_at": current + TOKEN_TTL,
    }
    access_tokens[access_token] = token_record
    refresh_tokens[refresh_token] = {
        "scope": scope,
        "resource": resource,
        "issued_at": current,
        "expires_at": current + REFRESH_TTL,
    }
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL,
        "scope": scope,
    }


async def token(request: web.Request) -> web.Response:
    data = await parse_token_request(request)
    if not client_auth_ok(request, data):
        return json_response({"error": "invalid_client"}, status=401)

    cleanup_expired()
    grant_type = data.get("grant_type", "")
    if grant_type == "authorization_code":
        code = data.get("code", "")
        record = auth_codes.pop(code, None)
        if not record:
            return json_response({"error": "invalid_grant"}, status=400)
        if data.get("redirect_uri") != record["redirect_uri"]:
            return json_response({"error": "invalid_grant"}, status=400)
        if pkce_s256(data.get("code_verifier", "")) != record["code_challenge"]:
            return json_response({"error": "invalid_grant"}, status=400)
        return json_response(issue_tokens(record["scope"], record["resource"]))

    if grant_type == "refresh_token":
        refresh_token = data.get("refresh_token", "")
        record = refresh_tokens.get(refresh_token)
        if not record:
            return json_response({"error": "invalid_grant"}, status=400)
        return json_response(issue_tokens(record["scope"], record["resource"]))

    return json_response({"error": "unsupported_grant_type"}, status=400)


async def introspect(request: web.Request) -> web.Response:
    data = await parse_token_request(request)
    if not client_auth_ok(request, data):
        return json_response({"active": False}, status=401)

    cleanup_expired()
    token_value = data.get("token", "")
    record = access_tokens.get(token_value)
    if not record:
        return json_response({"active": False})

    return json_response(
        {
            "active": True,
            "client_id": OAUTH_CLIENT_ID,
            "scope": record["scope"],
            "aud": record["resource"],
            "exp": record["expires_at"],
            "iat": record["issued_at"],
            "iss": base_url(request),
            "sub": OAUTH_USERNAME,
        }
    )


def bearer_record(request: web.Request) -> dict[str, Any] | None:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token_value = auth.split(" ", 1)[1].strip()
    cleanup_expired()
    return access_tokens.get(token_value)


def unauthorized(request: web.Request) -> web.Response:
    root = base_url(request)
    headers = cors_headers()
    headers["WWW-Authenticate"] = (
        f'Bearer realm="trvl", resource_metadata="{root}/.well-known/oauth-protected-resource"'
    )
    return web.Response(text="unauthorized\n", status=401, headers=headers)


async def proxy(request: web.Request) -> web.StreamResponse:
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=cors_headers())

    if not bearer_record(request):
        return unauthorized(request)

    upstream_url = f"{UPSTREAM_BASE_URL}{request.rel_url}"
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "authorization", "content-length"}
    }
    headers["Authorization"] = f"Bearer {UPSTREAM_BEARER_TOKEN}"

    body = await request.read()
    timeout = ClientTimeout(total=None, sock_connect=30)
    async with ClientSession(timeout=timeout) as session:
        async with session.request(
            request.method,
            upstream_url,
            headers=headers,
            data=body if body else None,
            allow_redirects=False,
        ) as upstream:
            response_headers = {
                key: value
                for key, value in upstream.headers.items()
                if key.lower() not in {"content-length", "transfer-encoding", "connection"}
            }
            response_headers.update(cors_headers())
            response = web.StreamResponse(status=upstream.status, headers=response_headers)
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(8192):
                await response.write(chunk)
            await response.write_eof()
            return response


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/.well-known/oauth-protected-resource", protected_resource_metadata)
    app.router.add_get("/.well-known/oauth-protected-resource/{tail:.*}", protected_resource_metadata)
    app.router.add_get("/.well-known/oauth-authorization-server", authorization_server_metadata)
    app.router.add_get("/.well-known/openid-configuration", authorization_server_metadata)
    app.router.add_get("/authorize", authorize_get)
    app.router.add_post("/authorize", authorize_post)
    app.router.add_post("/token", token)
    app.router.add_post("/introspect", introspect)
    app.router.add_route("*", "/{tail:.*}", proxy)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=int(env("PORT", "8080")))
