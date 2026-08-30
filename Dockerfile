FROM alpine:3.22

ARG TRVL_VERSION=1.21.4
ARG TRVL_SHA256=e6ec70d1718a590e1bd808793531ebb75547a931bc1c5ad682d00efd585d3daf

RUN apk add --no-cache ca-certificates curl \
    && curl -fsSL --retry 3 \
      "https://github.com/MikkoParkkola/trvl/releases/download/v${TRVL_VERSION}/trvl_${TRVL_VERSION}_linux_amd64.tar.gz" \
      -o /tmp/trvl.tar.gz \
    && echo "${TRVL_SHA256}  /tmp/trvl.tar.gz" | sha256sum -c - \
    && tar --no-same-owner -xzf /tmp/trvl.tar.gz -C /usr/local/bin trvl \
    && chmod 0755 /usr/local/bin/trvl \
    && rm /tmp/trvl.tar.gz \
    && addgroup -S trvl \
    && adduser -S -G trvl -h /home/trvl trvl \
    && mkdir -p /home/trvl/.trvl \
    && chown -R trvl:trvl /home/trvl

ENV HOME=/home/trvl \
    TRVL_NO_BROWSER_COOKIES=1 \
    TRVL_NO_TIER2_CDP=1 \
    TRVL_NO_TELEMETRY=1

USER trvl
WORKDIR /home/trvl

VOLUME ["/home/trvl/.trvl"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/health >/dev/null || exit 1

ENTRYPOINT ["trvl"]
CMD ["mcp", "--http", "--host", "0.0.0.0", "--port", "8080"]
