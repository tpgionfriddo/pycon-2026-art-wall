# The stack is containerised; the render worker drives the host Docker daemon

The whole system is one Compose stack (`compose.yaml`): a reverse proxy, the
submission server, one render worker, and a build-only service that produces
the sandbox image. The render worker runs in a container of its own but starts
each job's sandbox on the **host's** Docker daemon, through the host socket
mounted into it.

This supersedes ADR-0002's host-side worker process. Everything else ADR-0002
decides — SQLite as the queue, one short-lived hardened container per job, a
server that never touches Docker — is unchanged.

Two requirements follow, and both fail silently rather than loudly:

- **The host Docker socket** (`/var/run/docker.sock`) is mounted into the
  worker. Without it the worker has no daemon to start a sandbox on.
- **The worker's scratch area is bind-mounted at one identical absolute path
  inside and outside the container.** The daemon resolves bind-mount sources
  on the host, not in the filesystem of the process asking it, so a path that
  exists only inside the worker's container makes the daemon create an empty
  directory there and mount it *over* the submission's source — failing every
  render with an error that reads like broken attendee code. `compose.yaml`
  bind-mounts `ARTWALL_SCRATCH_DIR` onto itself for exactly this reason, and
  `check_scratch_base` in `artwall/worker.py` refuses to start on a base that
  cannot hold.

The same host-side resolution decides two more things that look arbitrary:

- **The proxy's configuration is baked into its image rather than
  bind-mounted.** Production deploys as a Portainer git stack, whose checkout
  directory does not exist on the host, so `./Caddyfile:/etc/caddy/Caddyfile`
  would quietly become an empty directory and the proxy would answer nothing.
  A build context is streamed to the daemon instead, so it arrives wherever
  Compose runs (`proxy/Dockerfile`).
- **`ARTWALL_DATA_DIR` must be absolute in production.** A relative path
  resolves against a host directory that does not exist, and the database
  lands somewhere nobody will think to look.

**The proxy is the only service that publishes ports, and it terminates TLS.**
One variable, `ARTWALL_SITE_ADDRESS`, is both the address it answers to and
the switch: a bare domain makes it obtain and renew a certificate itself; a
bare, hostless port serves plain HTTP for the booth-laptop fallback
(ADR-0004), where the TV reaches the laptop by its address on the venue
network. The server therefore publishes no host port, and runs with
`--proxy-headers --forwarded-allow-ips '*'`. Trusting every source is safe
only because the proxy is the sole route to the server, and the proxy
*replaces* `X-Forwarded-For` rather than appending to it: uvicorn reads the
leftmost entry, so appending would let an attendee mint a fresh address per
request and step around the submission rate limit entirely.

## Considered options

- **The host-side worker process of ADR-0002** — rejected once the stack
  became the unit of deployment. It is one more thing to start, supervise and
  remember on the VPS, and *Pull and redeploy* would not have shipped a fix to
  it along with the rest of the stack.
- **Docker-in-Docker for the worker** — rejected. It needs a privileged
  container, a larger grant than the socket, and the sandbox image would then
  have to be rebuilt inside the worker on every start rather than once on the
  box.
- **A bind-mounted Caddyfile** — rejected; it does not survive a Portainer git
  stack, as above.
- **Terminating TLS at the server** — rejected: certificate issuance and
  renewal would become application code, and ADR-0004's laptop fallback has no
  domain to certify.

## Consequences

- **The worker container has root-equivalent control of the host.** A mounted
  Docker socket is exactly that, and no capability dropping on the worker
  changes it. What makes it acceptable is where attendee code runs: never in
  the worker, only in the per-job sandbox the worker starts, which keeps
  ADR-0002's hardening — `--network none`, memory/CPU/pids limits, all
  capabilities dropped, no privilege escalation, and a host-side kill.
- **The sandbox image is built on the box, not by the stack.**
  `sandbox-image` sits behind a Compose profile nothing enables, so `up` skips
  it, and it must be rebuilt by hand whenever `worker/Dockerfile` or the
  Supported Packages (ADR-0001) change. See README, "Deploying to the VPS".
- **The scratch mount, the absolute data directory and the header replacement
  are each one edited line from breaking silently**, and none is covered by an
  automated test — the deployment stack is verified by the pre-flight
  checklist instead. `check_scratch_base` is the only one of the three that
  fails loudly.
- Certificates live in a named volume, so a redeploy does not re-issue them.
  There is deliberately no ACME contact address: renewal does not need one,
  and a certificate issued at the booth outlives the booth.
- A wall that will not load may now be the proxy rather than the server. The
  proxy is a fourth container in front of everything.
- Operating all of this is `docs/RUNBOOK.md`.
