# trvl for CapRover

Personal CapRover deployment for [trvl](https://github.com/MikkoParkkola/trvl), a travel MCP server and CLI for flights, accommodation, trains, cars and ferries.

The repository builds a pinned, checksum-verified trvl release and publishes it as:

```text
ghcr.io/tylonhh/trvl-caprover:latest
```

## One-click installation

1. In CapRover, open **Apps → One-Click Apps/Databases**.
2. Select **TEMPLATE** at the bottom of the app list.
3. Paste the contents of [`caprover-one-click.yml`](./caprover-one-click.yml).
4. Keep the generated 64-byte bearer token or enter your own secret.
5. Deploy the app.
6. In the app's **HTTP Settings**, enable **HTTPS** and **Force HTTPS**.
7. Verify `https://APP.YOUR-CAPROVER-DOMAIN/health`.

The MCP endpoint is:

```text
https://APP.YOUR-CAPROVER-DOMAIN/mcp
```

Configure the value of `TRVL_MCP_TOKEN` as the Bearer token in your MCP client.

## Persistent data

The template creates one named volume mounted at `/home/trvl/.trvl`. It stores preferences, traveller profile, trips, price watches, caches and provider health history. Back up this volume before replacing or deleting the app.

## Security defaults

- Remote access requires `TRVL_MCP_TOKEN`; trvl refuses to start without authentication.
- TLS is terminated by CapRover. Enable HTTPS before connecting an MCP client.
- Browser-cookie access and headless-browser fallback are disabled in the container.
- Anonymous trvl telemetry is disabled.
- The operational `/health` endpoint exposes only aggregate status. The `/dashboard` endpoint requires the Bearer token when remotely exposed.
- Never commit the token to this repository.

For a single-user installation a long static bearer token is the simplest option. For a multi-user or public service, use the upstream OAuth 2.1 introspection setup instead.

## Updating trvl

Update both values in `Dockerfile`:

- `TRVL_VERSION`
- `TRVL_SHA256` for the matching `linux_amd64` release archive

Commit the change. GitHub Actions will build and publish a new `latest` image. In CapRover, deploy the latest image again.

## License notice

This repository contains deployment configuration only. trvl itself is licensed under PolyForm Noncommercial 1.0.0 and remains the work of its upstream authors. This setup is intended for personal, noncommercial use. Review the [upstream license](https://github.com/MikkoParkkola/trvl/blob/main/LICENSE) before other use.
