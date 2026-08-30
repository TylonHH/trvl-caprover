# trvl for CapRover

Personal CapRover deployment for [trvl](https://github.com/MikkoParkkola/trvl), a travel MCP server and CLI for flights, accommodation, trains, cars and ferries.

The repository builds a pinned, checksum-verified trvl release and publishes two images:

```text
ghcr.io/tylonhh/trvl-caprover:latest
ghcr.io/tylonhh/trvl-caprover-oauth:latest
```

`trvl-caprover` is the original bearer-token MCP server image. `trvl-caprover-oauth` runs trvl internally on `127.0.0.1` and exposes a small OAuth 2.1 compatible bridge for ChatGPT Developer Mode and Codex HTTP MCP clients.

## One-click installation

1. In CapRover, open **Apps → One-Click Apps/Databases**.
2. Select **TEMPLATE** at the bottom of the app list.
3. Paste the contents of [`caprover-one-click.yml`](./caprover-one-click.yml).
4. Keep the generated OAuth password and OAuth client secret.
5. Deploy the app.
6. In the app's **HTTP Settings**, enable **HTTPS** and **Force HTTPS**.
7. Verify `https://APP.YOUR-CAPROVER-DOMAIN/health`.

The MCP endpoint is:

```text
https://APP.YOUR-CAPROVER-DOMAIN/mcp
```

Use OAuth authentication in ChatGPT Developer Mode.

Suggested static OAuth settings:

| Field | Value |
| --- | --- |
| Authorization URL | `https://APP.YOUR-CAPROVER-DOMAIN/authorize` |
| Token URL | `https://APP.YOUR-CAPROVER-DOMAIN/token` |
| Client ID | the `OAuth client ID` from the CapRover template |
| Client Secret | the `OAuth client secret` from the CapRover template |
| Scope | `trvl` |

When the browser login page opens, sign in with the OAuth username and password from the CapRover template.

The bridge also exposes the discovery endpoints ChatGPT-compatible MCP clients expect:

- `/.well-known/oauth-protected-resource`
- `/.well-known/oauth-authorization-server`

## Persistent data

The template creates one named volume mounted at `/home/trvl/.trvl`. It stores preferences, traveller profile, trips, price watches, caches and provider health history. Back up this volume before replacing or deleting the app.

## Security defaults

- Public remote access requires OAuth.
- trvl still requires a long random bearer token internally; it only listens on `127.0.0.1` inside the container.
- TLS is terminated by CapRover. Enable HTTPS before connecting an MCP client.
- Browser-cookie access and headless-browser fallback are disabled in the container.
- Anonymous trvl telemetry is disabled.
- The operational `/health` endpoint exposes only aggregate status.
- Never commit generated passwords, OAuth client secrets or bearer tokens to this repository.

This bridge is intentionally small and intended for a personal/single-user deployment. For a production multi-user service, use an established OAuth identity provider.

## Existing bearer-token deployments

The original single-image deployment still works if you deploy `ghcr.io/tylonhh/trvl-caprover:latest` directly and configure `TRVL_MCP_TOKEN`. The bundled one-click template now defaults to the OAuth bridge because ChatGPT web/app does not accept arbitrary custom bearer tokens for Developer Mode MCP apps.

## Updating trvl

Update both values in `Dockerfile`:

- `TRVL_VERSION`
- `TRVL_SHA256` for the matching `linux_amd64` release archive

Commit the change. GitHub Actions will build and publish a new `latest` image. In CapRover, deploy the latest image again.

## License notice

This repository contains deployment configuration only. trvl itself is licensed under PolyForm Noncommercial 1.0.0 and remains the work of its upstream authors. This setup is intended for personal, noncommercial use. Review the [upstream license](https://github.com/MikkoParkkola/trvl/blob/main/LICENSE) before other use.
