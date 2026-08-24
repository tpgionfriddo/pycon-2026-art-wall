# The stack's reverse proxy.
#
# The Caddyfile is baked in rather than bind-mounted from the repository,
# because the Docker daemon resolves bind-mount sources on the host and a
# Portainer git stack's directory does not exist there: the mount would
# quietly become an empty directory and the proxy would answer nothing. That
# is the same trap as the worker's scratch area (issue 04). A build context
# is streamed to the daemon instead, so it arrives wherever Compose runs.
#
#   docker build -t artwall-proxy proxy/
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
