FROM node:22-bookworm-slim

ARG OPENCODE_TELEGRAM_BOT_VERSION=0.22.1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      g++ \
      make \
      python3 \
      tini && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g "@grinev/opencode-telegram-bot@${OPENCODE_TELEGRAM_BOT_VERSION}" && \
    npm cache clean --force

ENV OPENCODE_TELEGRAM_HOME=/data

RUN mkdir -p /data

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/entrypoint.sh"]
