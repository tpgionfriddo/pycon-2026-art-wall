# Runbook — Code Art Wall at the booth

For whoever is standing at the booth when something goes wrong. Each section
is a symptom, then what to do about it. Everything here is a button in
Portainer except the one procedure whose heading says otherwise.

Design background is elsewhere — [decision records](adr/) and
[vocabulary](../CONTEXT.md). Don't read those now.

## Three things that are true before you start

1. **Nothing reaches the wall without a moderator.** Whatever is broken, no
   attendee can put something on the booth TV on their own.
2. **The queue is the database.** Restarting anything is safe: submissions
   that were waiting are still waiting afterwards, and a piece that was
   half-rendered goes back in the queue. Nothing is lost by a restart.
3. **One bad submission cannot stop the queue.** It is marked failed, the
   attendee sees why on their own status page, and the next piece renders.
   So a stopped queue is never "someone submitted something weird".

## What is running

Three containers, all the time:

| Container | What it does | If it's down |
| --- | --- | --- |
| `…-proxy-1` | The front door. Handles `https://` and passes everything inward. | No page loads at all, wall included. |
| `…-server-1` | The submission page, the wall, the moderation queue. | Pages fail; the wall shows "No pieces yet". |
| `…-worker-1` | Renders submissions, one at a time. | Queue stops moving; wall stops gaining pieces. |

The `…` is the stack's name. Find the real names with
`docker ps --format '{{.Names}}'`, or read the list in Portainer under
*Containers*.

Plus a container that comes and goes: each submission is rendered inside a
short-lived one named `artwall-job-<number>`, started by the worker and gone
within a minute. Seeing one appear and vanish is the system working.

**One naming trap.** That short-lived container runs an image tagged
`artwall-worker`. It is *not* the worker — the worker is the container above
that never stops. The image is what a submission is rendered inside, and it
is the thing that has to be built by hand on the box.

**Two ways to do anything below:** Portainer in a browser (*Containers* →
pick one → *Restart* / *Logs*), or SSH to the box. Portainer is the one to
reach for under pressure.

---

## The queue has stopped moving

**Symptom.** `/admin` shows a `queued` count that only grows, **oldest
queued** reads more than a few minutes, and `failed` is not moving either.
Nothing is being rendered at all.

**First, is it actually stopped?** One piece takes up to 60 seconds. A rush
with **oldest queued: 3 min** is a busy queue. Ten minutes and climbing,
with nothing arriving for moderation, is stopped.

Read this symptom precisely: it means the worker is not running. If pieces
*are* being picked up but every one of them fails, that is the next section
instead — `failed` would be climbing and `queued` draining.

1. **Check whether `…-worker-1` is up**, in Portainer under *Containers*. A
   container that is stopped, or restarting over and over, is the answer.
2. **Restart it** (see "Restarting a container"). This fixes almost every
   case and costs about ten seconds.
3. **If it exits again immediately**, its log says why on the last line:
   - **A line about the scratch base** — `ARTWALL_SCRATCH_DIR` is wrong, and
     the worker deliberately refuses to start rather than fail every render
     with a confusing error. It must be an absolute path that exists on the
     box. Fix it in the stack's environment variables and redeploy: this is
     a settings change, not a code change.
   - **Anything else on exit** needs whoever set the box up.
4. **Attendees seeing "Render queue is full. Try again later."** is this same
   problem from the other side: new submissions are refused once a hundred
   are waiting. Getting the worker back drains it.

## Every submission is failing

**Symptom.** The `failed` count climbs steadily, `queued` drains rather than
growing, and attendees see an error on their own status page within seconds
of submitting. The worker is running; it is the rendering that cannot work.

Almost always one of two things, and the worker's log names which:

- **`Unable to find image 'artwall-worker:latest' locally`**, followed by
  `pull access denied` — the sandbox image was never built on this box, or
  was built under another name. Build it: README, "Deploying to the VPS",
  *The sandbox image*. Nothing else fixes this; there is no such image
  anywhere to download.
- **Anything naming `/var/run/docker.sock`, or *permission denied*** — the
  worker cannot reach the Docker daemon it renders with. This one needs
  whoever set the box up (ADR-0007).

Submissions that failed this way still have their code stored, but nothing
re-renders them. Once the log is clean, ask those attendees to submit again.

## Good pieces are being killed for taking too long

**Symptom.** Attendees see **"render exceeded 180 s and was killed"** on their
status page. The worker log names the same thing. It is not every submission
— simple pieces still work — and the pieces being killed are animated ones.

**Why.** An animated piece is 150 frames. A `draw(t)` that takes a quarter of
a second looks instant in the preview, which draws one frame at a time in the
browser, and then costs nearly forty seconds here. The ceiling is whole-piece,
so the frame count multiplies whatever the code costs.

The other half is this box. The slowest shipped Example renders in about 15 s
on one dedicated CPU. Halving a container's CPU was measured to cost about
3.3x rather than 2x, so a host whose CPU is shared or oversubscribed puts that
same piece near 50 s, and anything heavier past the ceiling.

**Check which it is.** Run `booth-render-timing.py` from the repo on this box.
It renders the seven Examples through the real sandbox, writes nothing to the
database, and prints each one against the reference measured on a dev laptop.
If the Examples are several times slower here, the box is the problem and the
ceiling is only where you notice.

**The fix, right now:** raise `ARTWALL_RENDER_TIMEOUT_S` and restart the
worker. It is a stack variable, so this is an edit in Portainer and a restart
rather than a commit and a redeploy. Nothing queued is lost.

Two things to know before you raise it a long way. The worker renders one job
at a time, so the ceiling is also the longest anybody queued behind a slow
piece waits. And if the box is simply short of CPU, a bigger ceiling does not
make successful pieces arrive any sooner — it only stops them being thrown
away.

**Do not remove the ceiling.** It is the only thing bounding a submission that
never finishes. `--memory`, `--pids-limit` and `--cpus` do not stop
`while True: pass`; the first one to arrive would hold the single worker
forever, the queue would fill to `ARTWALL_MAX_QUEUE_DEPTH` and `/submit`
would start refusing everybody. Restarting the worker does not clear it
either: a `rendering` row is handed straight back to the queue on startup, so
the same piece hangs again. Recovering would mean deleting that row from
SQLite by hand, mid-event.

Killed submissions keep their code, but nothing re-renders them. Once the
ceiling is right, ask those attendees to submit again.

## The wall is blank

**Symptom.** The booth TV shows the header and *"No pieces yet — be the
first on the wall!"*, or nothing at all.

Work down this list in order; the first two are far more likely than the
rest.

1. **Is anything approved?** *"No pieces yet"* with an empty **On the wall**
   section in `/admin` is the wall working perfectly. Approve something.
2. **Reload the page** on the TV. The wall looks for new pieces every five
   seconds and deliberately ignores errors, so a flaky venue network doesn't
   blank it — which also means a network blip can leave it quietly behind.
3. **Careful: "No pieces yet" cannot tell you the server is down.** If the
   page loaded a while ago and the server has since stopped, the wall keeps
   showing that same message. So if `/admin` also fails to load from a
   laptop, believe `/admin`, not the wall.
4. **No page loads at all, anywhere** — the front door. Restart
   `…-proxy-1`, then `…-server-1`. Because the proxy sits in front of
   everything, a dead proxy and a dead server look identical from the TV.
5. **Tiles are there but the pictures are broken** — the rendered media is
   not where the server expects it, most likely `ARTWALL_DATA_DIR` pointing
   somewhere new after a redeploy. Whoever deployed it needs to look. The
   source code for every piece is safe in the database, but re-rendering one
   needs database access, so treat missing media as lost for the event.
6. **`https://` fails but `http://` works** — the certificate. Check the
   `…-proxy-1` log. If one never issued, the wall can run on `http://` for
   now; attendees on mobile data are the ones who need HTTPS.

## Attendees are told "Too many submissions"

**Symptom.** Someone who has submitted nothing, or one piece, is refused
with **"Too many submissions. Try again later."**.

**Why.** Submissions are capped *per network address*, not per person, and
venue Wi-Fi puts the whole hall behind one. The default is sixty per ten
minutes, set to clear a hall rather than a person, so seeing this at all
means either an unusually busy ten minutes or one attendee submitting hard.

**The fix, right now:** restart `…-server-1`. The counts are kept in memory,
so a restart clears every one of them instantly. It costs nothing — no
queued submission is lost and nothing on the wall changes. Do it as often as
it takes.

If it keeps happening, raise the ceiling: `ARTWALL_RATE_LIMIT_MAX` and
`ARTWALL_RATE_LIMIT_WINDOW_S` are stack variables, so this is an edit in
Portainer and a restart rather than a commit and a redeploy.

## The wall is stuttering

Animated pieces are WebM/VP9, and a TV browser without hardware decoding for
it may stumble with dozens of tiles playing at once (ADR-0003). The response
is pre-specified so nobody has to debug it live, **in this order**:

0. **Right now:** reload the wall. That is everything available without
   shipping a change, and worth trying — a wall that has been open for hours
   is not a fresh one.

   **Do not take pieces down to relieve it.** It would help, and it is the
   wrong trade: a takedown cannot be undone from the moderation queue (see
   below), so a temporary problem would permanently cost attendees their
   place on the wall.
1. **Cap how many pieces animate at once.** *First*, because it works on
   pieces that are **already approved** — the whole wall improves at once.
   **There is no setting for this today**, so it needs someone who can ship
   a change to the wall page. It is a small one.
2. **Only then, move off VP9** (ADR-0003 carries the detail and the cost).
   *Second*, because it affects **new pieces only**: everything already on
   the wall keeps stuttering, and nothing re-renders it.

Do not reorder these. Step 2 first looks like it did nothing, because the
pieces already on the screen are the ones causing the problem.

## A piece must come off the wall

1. `/admin` → the **On the wall** section → **Take down** on that piece.
2. **Reload the wall on the TV.** The wall does not remove tiles by itself,
   on purpose; the takedown lands on the next load.

**A takedown cannot be undone here.** There is no button that puts a piece
back; a mistake needs someone with database access. So read the card — the
number and the byline — before clicking, especially with several similar
pieces side by side.

A takedown is not the same as a reject, and that matters afterwards: a
rejected piece was never seen by anyone, a taken-down one was. Both stay in
the CSV export, so the record of what the crowd actually saw survives.

If you cannot reach `/admin` at all and a piece has to go **now**, the wall
is a browser page — close the tab. An empty screen beats the wrong piece.

## Restarting a container

Any of the three is safe to restart at any time, including mid-render.

- **Portainer:** *Containers* → tick the one you want → **Restart**.
- **SSH:**
  ```bash
  docker ps --format '{{.Names}}'    # find the exact names
  docker restart artwall-worker-1    # or …-server-1, or …-proxy-1
  ```

**The worker** takes about ten seconds. Watch its log: `requeued N job(s)
left over from a crash` means a piece that was mid-render went back into the
queue, and `polling …` means it is working again. Nothing queued is lost,
because the queue lives in the database.

**The server** drops whatever page anyone had half-loaded, and clears every
submission rate-limit count — which is the fix for "Attendees are told 'Too
many submissions'" above, not merely a side effect.

**The proxy** is the front door: while it restarts, *nothing* loads, wall
included. It returns in a couple of seconds and does not re-issue
certificates, which live in a volume of their own. Restart it when pages
fail everywhere at once but the server itself looks healthy.

## Restoring the database — get someone with a shell

**This is the one procedure here that Portainer cannot do, and the one that
booth staff should hand to whoever set the box up.** Everything else above
is a button. This is file surgery, and doing it wrong loses the contact
list.

The database is the only thing here that cannot be rebuilt: it holds every
submission's source code, the contact list, and the moderation record.
Rendered media is deliberately not backed up, because the source code behind
every piece is in the database — though re-rendering needs database access
too, so treat lost media as lost for the event.

**Before anything else, know what you have.** Automatic hourly snapshots are
not built yet. The only copies that exist today are ones a person made by
hand, and if nobody made one there is nothing to restore — stop there rather
than making it worse.

**Find the real directory first.** `ARTWALL_DATA_DIR` is a *stack* variable,
not a shell one: over SSH it is unset, so never `cd` to it. Ask Docker where
the data actually is:

```bash
docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' artwall-server-1
```

The line ending `-> /data` is the host directory. The steps below assume you
have replaced `/srv/artwall/data` with that literal path.

**Taking a copy** — do this first if none exists; it is the cheap half, and
it is safe while the stack is running, which a plain `cp` is not:

```bash
docker exec -i artwall-server-1 python - <<'PY'
import sqlite3
src = sqlite3.connect("/data/artwall.db")
dst = sqlite3.connect("/data/snapshot.db")
src.backup(dst)                 # SQLite's own snapshot, safe under WAL
dst.close(); src.close()
PY
```

That leaves `snapshot.db` in the same host directory. Rename it with today's
date and copy it off the box.

**Restoring one:**

1. **Stop the stack.** Portainer: *Stacks* → the stack → **Stop**. Not
   optional: replacing files under a running system turns one problem into
   two.
2. **Move the current files aside rather than deleting them**, even if they
   look ruined. There are up to three, not one:
   ```bash
   cd /srv/artwall/data          # the path you found above
   mkdir -p broken
   mv artwall.db artwall.db-wal artwall.db-shm broken/
   ```
   The `-wal` and `-shm` may not exist. An error naming only those two is
   fine — read it rather than hiding it.
3. **Put the copy in place** as `artwall.db`. Check no `-wal` or `-shm` file
   from the old database is left beside it: a stale one is read in
   preference to the file you just restored, and you get the old data back
   with no error at all.
4. **Start the stack**, open `/admin`, and check the counts look like the
   event you remember. That is the whole verification.

## Exporting the contact list

`/admin` → **Export CSV**, top right. Any username; the password is the
moderator one.

Every submission at every status — including rejected and taken-down — with
the byline and the marketing permission each attendee gave.

It also carries each attendee's first and last name, email, and the phone
number and company they may have given. Treat the file as personal data:
it goes somewhere the organisers control, not a shared laptop or a chat
thread.

**Do this before the stack is torn down at the end of the event.** It is the
artefact the booth exists to produce, and the one thing here that nobody can
reconstruct later.

---

## Safe to ignore until after the event

Don't spend booth time on any of these.

- **Individual failed submissions.** The attendee already sees the reason on
  their own status page. A `failed` count that climbs slowly is the system
  working. (A `failed` count climbing on *every* submission is not — that is
  "Every submission is failing" above.)
- **A growing `rejected` or `removed` count.** That is the record, not a
  fault.
- **Soft or slightly blurry tiles** when only a few pieces are up. Pieces
  are rendered no larger than a fixed cap, and the browser scales them up to
  fill the tile without distorting them. Expected (ADR-0005).
- **The moderation page redrawing itself** while you watch it. It re-reads the
  queue every few seconds and reloads when a submission arrives.
- **A "refresh" link in the moderation page's header.** It is holding a reload
  back rather than moving cards you may be about to click, or closing a source
  view you are reading. Click it when you are ready.
- **A "new piece" toast you missed** on the wall. Nothing is lost; the piece
  is on the wall.
- **A page briefly rendering in the wrong font.** It comes from a CDN over
  venue Wi-Fi. Cosmetic.
- **No certificate-expiry warnings arriving.** There is deliberately no
  contact address for them, and renewal does not need one (ADR-0007).
- **Slow deploys and a large image.** Known; costs time and nothing else.

## Not safe to ignore

- **A queue that has stopped moving** — the wall silently stops growing, and
  attendees wait for a piece that will never appear.
- **Every submission failing** — attendees are being turned away one at a
  time, each of them thinking their own code was at fault.
- **A wall that will not load** on the TV. It is the booth.
- **Not having taken the CSV export** before the stack comes down.
