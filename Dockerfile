# Application image: the server and the render worker, from one image.
# The sandbox attendee code runs in is a different image entirely — see
# worker/Dockerfile — and nothing here ever executes a submission.
#
#   docker build -t artwall-app .
FROM python:3.12-slim

# The worker starts each job's sandbox by shelling out to `docker` (ADR-0002),
# so the client has to be in the image. Only the client: the daemon it talks to
# is the host's, reached through a socket mounted into the worker, and this
# container never runs a daemon of its own.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
         -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture)" \
            "signed-by=/etc/apt/keyrings/docker.asc]" \
            "https://download.docker.com/linux/debian" \
            "$(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
         > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && apt-get purge -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/mpl

# Dependencies first, so editing the source does not reinstall them. The
# project itself declares no build backend, so `uv sync` resolves the lock
# into the venv and `artwall` is imported from the working directory.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY artwall ./artwall

# Both services run this image; Compose supplies the command that picks one.
CMD ["python", "-m", "artwall.worker"]
