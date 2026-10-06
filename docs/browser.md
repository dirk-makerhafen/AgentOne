# Browser (Camoufox)

AgentOne agents get a real browser: a persistent, headful
[Camoufox](https://github.com/daijro/camoufox) instance with multiple tabs,
real cookies and logins, downloads, uploads, screenshots, and arbitrary JS.
It is exposed as a single multiplexed tool, `browser(action=...)`.

## Setup

```bash
pip install -r requirements.txt            # includes camoufox==0.5.7
python3 manage.py server browser fetch     # one-time browser download (~1.3 GB)
python3 manage.py server browser status    # confirm it is detected
```

Pinning `camoufox==0.5.7` also pins the browser build: the wheel ships a
`browser-pin.json` naming the exact Firefox build it was released and tested
with (`official 156.0.1-beta.34`), and `fetch` installs that build rather than
whatever is newest. Upgrading the package therefore upgrades the browser
together with it. Launching an explicitly re-selected build
(`camoufox set ...`) emits a RuntimeWarning when it differs from the paired one.

`manage.py server run` supervises the browser daemon alongside Daphne, Celery
worker, and Celery beat. It also starts on demand the first time an agent calls
`browser`, so `manage.py runserver` (no Celery) still works.

## Architecture

```
Celery worker (5 prefork)          Browser daemon (one process)
┌───────────────────────┐          ┌──────────────────────────────┐
│ browser tool          │  HTTPS   │ driver thread                │
│  resolve_scope()      │ ───────► │  sync_playwright()           │
│   (server-derived)    │  loopback│  registry: bindings + pages  │
└───────────────────────┘  +token  │  reaper thread (idle close)  │
                                   └──────────────┬───────────────┘
                                                  │
                                     ┌────────────┴─────────────┐
                                     │ Camoufox process (headful)│
                                     │  user_data/ = cookies,     │
                                     │  logins, localStorage      │
                                     └──────────────────────────┘
```

A daemon is required rather than module-level state in the tools: the Celery
pool is five prefork workers, so per-worker globals would create five
disconnected browsers and lose them on every worker restart. The daemon is
bound to `127.0.0.1` and requires a bearer token from
`~/.agentone/browser/token` (`0600`).

### Files

| Path | Role |
|---|---|
| `runtime/browser/config.py` | reads the `browser:` block of `~/.agentone/config.yaml` |
| `runtime/browser/paths.py` | profile/token/state/audit locations, profile-key validation |
| `runtime/browser/scope.py` | session → root session, profile key, ownership |
| `runtime/browser/launcher.py` | Camoufox launch options, stable identity, persistent launch |
| `runtime/browser/snapshot.py` | text DOM snapshots with `[ref]` element handles |
| `runtime/browser/policy.py` | domain allow/deny + navigation audit log |
| `runtime/browser/registry.py` | bindings (one process each), page ownership, idle/LRU reaping |
| `runtime/browser/daemon.py` | driver thread + local authenticated HTTP API |
| `runtime/browser/client.py` | tool-side client, token auth, lazy daemon start |
| `runtime/browser/actions.py` | action catalogue shared with the approval gate |
| `.agentone/scripts/browser/browser.py` | the `browser` tool |

Profiles live in `~/.agentone/browser/profiles/`, deliberately **not** under
`~/.agentone/runtime/` (which is garbage-collected versioned task state).

## Sessions, tabs, and ownership

| Caller | Browser | Tabs it may touch |
|---|---|---|
| Root chat session | its own process (profile `s<root_pk>`) | every tab in that browser |
| Child / subsession agent | **inherits** the root's browser | only tabs it opened itself |
| Another top-level session | separate process | its own tabs |
| `profile="name"` | shared with sessions using that name | still only its own tabs |

The scope is derived from the injected `session` object and
`SessionModel.parent_session`. The LLM cannot name another session's scope — it
can only pick between documented profiles (`profile="github"`) or ask for
`clean=True`. Cookies and logins are shared within a browser (that is the point
of inheriting it); *tab* access is not.

Root/subsession inheritance means one login works across the whole session
tree, while each agent still only drives its own tab.

## Actions

Read-only (no approval): `status`, `snapshot`, `read`, `tabs`, `cookies`,
`wait`, `close_tab`.

Mutating (park at `HALTED_APPROVAL`): `open`, `navigate`, `click`, `type`,
`back`, `evaluate`, `upload`, `download`.

| Action | Notes |
|---|---|
| `status` | live bindings, tabs, whether a browser build is installed |
| `open` | new tab, optional `url` |
| `navigate` | navigate a tab |
| `tabs` | tabs visible to this session |
| `snapshot` | text outline with `[e12]` refs — **the primary way to read a page** |
| `read` | readable text (prefers `<main>`/`<article>`) |
| `click` / `type` | target a `ref` or `selector`; `submit=True` presses Enter |
| `wait` | `ms`, or wait for a `ref`/`selector`/load |
| `back` | history back |
| `screenshot` | PNG into the workspace; pair with the `read_image` tool for vision |
| `upload` | file input from a workspace path |
| `download` | by `url` or by clicking a `ref` |
| `evaluate` | run JS in the page |
| `cookies` | names + domains only; **values are never returned** |

Refs are re-issued on every `snapshot` and rewritten by any page script.
Always `snapshot` immediately before acting.

Typical loop:

```
browser(action="open", url="example.com")
browser(action="snapshot")            -> read the refs
browser(action="type", ref="e3", text="hello", submit=True)
browser(action="snapshot")            -> refs changed; snapshot again
```

## Configuration

```yaml
# ~/.agentone/config.yaml
browser:
  mode: headful              # headful | headless
  scope: session             # session | named
  max_processes: 6           # concurrent browsers
  idle_seconds: 3600         # close a browser after this idle time (1h default)
  ephemeral_by_default: false
  block_images: false
  humanize: 1.5              # Camoufox cursor/typing humanisation
  enable_cache: true
  nav_timeout: 60            # per navigation / load-state wait
  action_timeout: 30         # per click / fill / press
  audit: true
  allow_domains: []          # empty = allow all
  deny_domains: []
```

Idle accounting uses the monotonic clock, so system sleep does not count as
idleness: closing the lid for lunch no longer reaps the browser. Note that
an idle eviction (or any browser restart) drops **session** cookies by
definition — sites that keep consent in session cookies (heise.de's
`consentUUID`/`consentDate`) will show their banner again afterwards. If that
bothers you, raise `idle_seconds` further rather than fighting the banner.

The daemon re-reads this file every couple of seconds, so edits apply without a
restart.

### Window behaviour

Headful by default — one visible window per active browser, which is what makes
manual login and CAPTCHA completion possible. `minimize: true` exists but is
off by default: Playwright exposes no supported minimize on macOS, and the
osascript workaround needs Accessibility permission, which would fire a system
permission prompt. Not worth it for a cosmetic gain.

## Persistent identity

Camoufox draws a full fingerprint (navigator, screen, fonts, WebGL, voices,
audio seed) at launch. New identities are drawn for the host OS, keeping the
claimed platform, font list, and native font handling coherent. Redrawing on
every reopen would make one persistent profile look like a different machine
each time. The generated options are therefore written once to
`<profile>/launch_options.json` and replayed with
`NewBrowser(from_options=...)` forever after, so an evicted or restarted
browser comes back as the same device. Already-persisted identities are not
migrated automatically.

What persists: cookies, logins, localStorage, and the fingerprint.
What does not: **open tabs** — page handles do not survive a browser-process
restart, so `tabs` is empty after a restart and the agent re-opens. This is
normal; it is not a lost session.

Session cookies (no `Max-Age`/`Expires`) are dropped by Firefox on close, as in
any browser.

## Security model

- **Page content is untrusted.** `snapshot`/`read` results carry an explicit
  notice. Instructions found in a page are data, not commands.
- **Mutating actions require approval** (`runtime/tasks/call_scheduler.py`,
  `_guardrail_browser_check`). `evaluate` is included because page JS can do
  anything the page can, including submitting a form the agent was only asked to
  read.
- **Filesystem paths are double-gated.** The manifest declares `access: write`,
  so the workspace policy applies; and the daemon independently refuses any
  path escaping the workspace root the tool passed in (defence in depth).
- **`file:` and `data:` URLs are not navigable** (`runtime/browser/policy.py`,
  `check_navigation`). Only `http:`, `https:`, and `about:` are allowed. The
  browser runs as the user, so a `file:` page would render arbitrary local files
  and hand them back through `snapshot`/`read` — a filesystem escape that no
  argument-level guardrail covers. To work with a local file, save it into the
  workspace and pass it as `path` (write) or `upload_path` (read) instead.
- **The daemon is authenticated.** Loopback only, `secrets.compare_digest`
  bearer token in a `0600` file, profiles `0700`. The token is not accepted as
  a query parameter (it would land in logs).
- **Domain policy is allow-all for now**, and every navigation is appended to
  `~/.agentone/browser/nav-audit.jsonl` with the session and profile that made
  it. Add `deny_domains`/`allow_domains` later without any tool change.
- Cookie **values** are never returned; only names and domains.
- The user's real browser profile is never used.

## Operational notes

```bash
python3 manage.py server browser status     # bindings, tabs, install check
python3 manage.py server browser profiles   # on-disk profiles
python3 manage.py server browser start      # start on demand
python3 manage.py server browser stop       # graceful shutdown
```

`status` and `stop` are read-only: they never start the daemon. Only the first
real `browser` tool call (or an explicit `start`, or `manage.py server run`)
spawns it.

Logs and state: `~/.agentone/browser/daemon.log`, `state.json` (pid + port),
`nav-audit.jsonl`.

Idle browsers are closed after `idle_seconds`; if the process count is at
`max_processes`, the least-recently-used browser is evicted first. Clean
(`clean=True`) profiles are deleted when their browser closes.

## Known limitations

- Tabs are not restored across daemon/browser restarts (cookies are).
- No cross-session tab sharing; a child agent sees only its own tabs. Cross-lineage
  capability handles are a possible future addition.
- One identity per profile; no per-tab identities.
- Browser build download is large (~1.3 GB for current builds).