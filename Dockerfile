FROM ghcr.io/astral-sh/uv:0.11.6-python3.14-trixie

# Pinned by versions.lock.json (auto-bumped via .github/workflows/upstream-release-watch.yml).
# Override at build time with --build-arg if needed.
ARG HERMES_REF
ARG HERMES_WEBUI_REF
ARG NPM_VERSION=11.17.0

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/hermes/.playwright \
    HERMES_HOME=/data \
    PATH="/opt/hermes/.venv/bin:/data/.local/bin:${PATH}" \
    PYTHONPATH="/opt/hermes-railway:/opt/hermes:/opt/hermes-webui"

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      docker-cli \
      ffmpeg \
      gcc \
      git \
      gosu \
      libffi-dev \
      nodejs \
      openssh-client \
      procps \
      python3 \
      python3-dev \
      ripgrep \
      tini && \
    npm install -g "npm@${NPM_VERSION}" && \
    node --version && \
    npm --version && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --system --uid 10000 --create-home --home-dir /home/hermes --shell /bin/bash hermes

COPY versions.lock.json /tmp/versions.lock.json

WORKDIR /opt/hermes

RUN set -eux; \
    HERMES_REF="${HERMES_REF:-$(python3 -c "import json; print(json.load(open('/tmp/versions.lock.json'))['hermes_agent'])")}"; \
    echo "Building Hermes Agent at ${HERMES_REF}"; \
    git init . && \
    git remote add origin https://github.com/NousResearch/hermes-agent.git && \
    (git fetch --depth 1 origin "${HERMES_REF}" || git fetch --depth 1 origin "refs/tags/${HERMES_REF}:refs/tags/${HERMES_REF}") && \
    git checkout --detach FETCH_HEAD

ENV npm_config_install_links=false

# Browser tools require a working Chromium installation. Fail the build rather
# than silently shipping an image without Playwright.
RUN npm install --prefer-offline --no-audit && \
    ( \
      if [ -x node_modules/.bin/playwright ]; then \
        ./node_modules/.bin/playwright install --with-deps chromium --only-shell; \
      else \
        npx --yes playwright install --with-deps chromium --only-shell; \
      fi \
    ) && \
    npx --yes playwright --version && \
    test -d "${PLAYWRIGHT_BROWSERS_PATH}" && \
    npm cache clean --force

# Pin the interpreter explicitly so uv does not honor an upstream
# `.python-version` and install a managed Python under root-only /root.
# Current Hermes releases gate core dependencies on Python 3.14; using an
# older interpreter silently omits those packages and crashes the gateway.
ENV UV_PYTHON=3.14

RUN uv venv --python 3.14 && \
    uv pip install --no-cache-dir -e ".[all,messaging]"

RUN chmod -R a+rX /opt/hermes

# Hermes WebUI: pure Python (stdlib + pyyaml) + vanilla JS, served from /opt/hermes-webui
WORKDIR /opt/hermes-webui

RUN set -eux; \
    HERMES_WEBUI_REF="${HERMES_WEBUI_REF:-$(python3 -c "import json; print(json.load(open('/tmp/versions.lock.json'))['hermes_webui'])")}"; \
    echo "Building Hermes WebUI at ${HERMES_WEBUI_REF}"; \
    git init . && \
    git remote add origin https://github.com/nesquena/hermes-webui.git && \
    (git fetch --depth 1 origin "refs/tags/${HERMES_WEBUI_REF}:refs/tags/${HERMES_WEBUI_REF}" || git fetch --depth 1 origin "${HERMES_WEBUI_REF}") && \
    git checkout --detach FETCH_HEAD && \
    uv pip install --python /opt/hermes/.venv/bin/python --no-cache-dir -r requirements.txt && \
    chmod -R a+rX /opt/hermes-webui

# Wrapper extras: small Starlette app that exposes /tui (in-browser xterm with
# OAuth shortcut buttons for `hermes auth add` device-code flows plus a free-
# form `/bin/bash` pane) and reverse-proxies everything else to hermes-webui on
# loopback (HERMES_WEBUI_HOST / HERMES_WEBUI_PORT; default 127.0.0.1:9120).
# starlette/uvicorn/httpx may already be transitive Hermes
# deps, but install explicitly to pin.
RUN uv pip install --python /opt/hermes/.venv/bin/python --no-cache-dir \
    ptyprocess httpx websockets starlette uvicorn

WORKDIR /opt/hermes-railway

COPY admin ./admin
COPY plugins ./plugins
COPY skills ./skills
COPY scripts ./scripts
COPY entrypoint.sh ./entrypoint.sh

# Owned by `hermes` so `git fetch`/`hermes update` from the Web TUI do not trip
# "detected dubious ownership" (repos owned by root, commands run as hermes).
RUN chmod +x \
      /opt/hermes-railway/entrypoint.sh \
      /opt/hermes-railway/scripts/prism-workspace-bootstrap.sh \
      /opt/hermes-railway/scripts/volume-hygiene.sh \
      /opt/hermes-railway/scripts/volume-maintain-loop.sh \
      /opt/hermes-railway/scripts/opencode-volume-maintain.sh && \
    mkdir -p /data && \
    chown -R hermes:hermes \
      /opt/hermes \
      /opt/hermes-webui \
      /data \
      /opt/hermes-railway && \
    git config --system --add safe.directory /opt/hermes && \
    git config --system --add safe.directory /opt/hermes-webui

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8080}/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/hermes-railway/entrypoint.sh"]
