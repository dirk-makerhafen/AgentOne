# Folder handling

Single source of truth for where AgentOne keeps things. Path logic lives in
`runtime/paths.py` — do not recompute `~/.agentone/...` paths elsewhere.

## Scopes (most-specific wins)

| Scope | Manifest dir | DB owner |
|---|---|---|
| `global` | `<repo>/.agentone/` (`settings.AGENTONE_ROOT`) | `parent_project=None` |
| `user` | `~/.agentone/{agents,skills,scripts}/` | `parent_project=None` (loads after global, user versions win) |
| `project` | `Project.agentone_dir` (legacy fallback `<path>/.agentone`) | `parent_project=<row>` |
| `workspace` | `Workspace.agentone_dir` | parent project's namespace (`parent_project=workspace.parent_project`) |

User manifests use the same layout as global (`agents/<n>/agent.md`,
`skills/<s>/skill.md`, `scripts/`). Missing dirs are skipped. Cron jobs
are DB-canonical (created/managed via the Web UI), not manifest files.
Workspace manifests require `parent_project` to be set, otherwise reload
warns and skips.

## DB-canonical metadata (deprecated files)

- **No `project.md`, no `projects.yaml`, no `workspace.md`.**
  `Project` (`agentone_dir`, `git_url/ref`, `main_workspace FK`)
  and `WorkspaceModel` (`parent_project FK`, `agentone_dir`,
  `access`) are the source of truth, edited via UI/API. Existing rows were
  kept as-is; the new fields are nullable with legacy fallbacks.
- Leftover `project.md` / `projects.yaml` files on disk are
  **warn-and-ignore**: reload emits a `warning` details entry and never
  creates/updates rows from them. Safe to delete.
- Only the resulting `agentone_dir` is stored — not the location type that
  produced it. The UI offers the usual defaults:
  - inline workspace: `<workspace>/.agentone/` (ignored by default; enable
    “Share/track `.agentone/` config in Git” to include it in the project repo).
  - project workspace: `<project agentone>/workspaces/<name>/`.
  - user workspace: `~/.agentone/workspaces/<name>/`.
  - project manifests live at `~/.agentone/projects/<name>/` when central.
  - git projects (future): row with `git_url/ref`, temp workspace on demand.
  - inline project manifests follow the same Git ignore/share choice as inline
    workspace manifests.

## Per-scope `var/`

Every scope directory is self-contained: manifests at the top level, runtime
state below `var/`.

```
<scope>/.agentone/                      # or ~/.agentone for global/user
├── agents/ skills/ scripts/ dashboard/ memory/
├── providers/                          # generated provider/model JSON (registry/catalog)
├── free/                               # final reviewed free dataset (merge_free_reviews)
└── var/
    ├── sessions/<agent>/<pk>/          # scope-only session scratch (0700)
    ├── log/                            # scope logs
    ├── run/                            # scope pids/locks
    └── cache/
        ├── runtime/<ver_pk>/           # version extracts (1h GC)
        ├── upstream/                   # upstream clones (global/user only)
        ├── staging/                    # merged staging (global/user only)
        ├── provider-catalog/           # raw upstream LLM catalog payloads (global/user only)
        └── free-tier/                  # free-tier dev inputs (global cache, never versioned)
            ├── candidates/             # generated leads (refresh_free)
            ├── reviews/                # curated agent verdicts (agent-written)
            └── leaderboard/            # downloaded scores + generated leaderboard.csv (sync_model_ranks)
```

The global manifest root is the repo's `.agentone/`, but its `var/` (like the
user scope's) is `~/.agentone/var` — so the free-tier dev inputs live at
`~/.agentone/var/cache/free-tier/`, outside the checkout. Only the reviewed
dataset (`<root>/free/`) is versioned.

`var/` is never versioned: add `var/` to each scope's `.gitignore` and the
install sync excludes it automatically.

## Machine-wide state under `~/.agentone/`

| Dir | Lifecycle |
|---|---|
| `var/sessions/<agent>/<pk>/` | Global/user-scope session scratch, lazy, `0700`. Own=allow, other/base=deny. Folders with files are kept forever (incl. archived); hard-deleted orphans and empty folders of ended (`is_active=False`) sessions are swept at startup and every ~10 min from the tick scheduler. Project/workspace sessions live in their own `<scope>/var/sessions/` and are swept too. |
| `var/cache/runtime/<ver_pk>/` | Global/user-scope version extracts + `.last_used`. GC after 1h idle, re-extracted on demand. Project/workspace extracts live in their own `var/cache/runtime/`. |
| `var/install/global\|user\|projects/<pk>\|workspaces/<pk>/` | Machine-wide git repos synced from scope source (`rsync --delete`), versioned by tree SHA. Keyed by stable scope identity (pk), not name. Re-syncable. |
| `var/browser/` | Daemon token (`0600`), profiles, audit log. **Durable — back up.** Outside runtime GC. Machine-wide: named profiles are shared across scopes. |
| `var/log/`, `var/run/` | Terminal logs (`var/log/terminals/`) and the sleep-guard pid (`var/run/`). Disposable. |
| `var/cache/upstream/*`, `var/cache/staging/*` | Upstream clones + merged staging (upstream first, local overlays; `sources.yaml` + `skills.yaml` are config-only, excluded; staging uses `--delete`). Re-syncable. |
| `var/cache/provider-catalog/` | Raw JSON downloads for `registry/catalog` (awesome-free-llm-apis, freellmapi-catalog, opencode-models-api) plus a fetch manifest. Re-syncable; see [provider-catalog.md](provider-catalog.md). |
| `var/cache/free-tier/` | Free-tier dev inputs: `candidates/` (re-generated by `refresh_free`), `reviews/` (curated verdicts) and `leaderboard/` (downloaded scores + generated `leaderboard.csv`, re-generated by `sync_model_ranks`). Re-creatable; the reviewed dataset is versioned in `<root>/free/` and the curated rank table in `docs/model-ranks.md`. |
| `memory/` | One local Git repo per global/project/workspace memory root. Legacy nested `.git` directories under that root are deleted during the next memory walk; memory files are retained, but their nested Git histories are discarded. |
| `workspaces/_assistant_scopes/<source path>/assistant_scope/` | Central data for **explicit** source-bound chats (e.g. `call_assistant` with a `context_path`). Rightbar assistant panels no longer create these — they bind AgentOne home, the project's primary workspace, or the selected workspace. Existing scope data is preserved. |
| `projects/<n>/`, `workspaces/<n>/` | Central manifest dirs (DB content). Back up with the DB. |
| `secrets/` | `django_secret_key`, `agent_server_secret_key` (`0600`). Never synced or versioned. |

## Reload (`run_reload_all`)

1. Global scope from staging-or-local root → install repo.
2. User scope (`~/.agentone/...`) into the global namespace.
3. DB loop: every `Project` row → `load_scope_dir(agentone_dir)`; every
    `WorkspaceModel` with `agentone_dir` → load under its `parent_project`.
   Missing dirs warn-and-skip; rows are never deleted (crons archive).
4. Orphan warnings (no autoscan/import by design):
   `~/.agentone/projects/*/` or `~/.agentone/workspaces/*/` with no matching
    `agentone_dir` row → `warning` entry ("create it in the UI or delete").
5. `projects.yaml` present → deprecation warning. `project.md` present →
   deprecation warning per file.

## Overrides

| Knob | Default | Via |
|---|---|---|
| `AGENTONE_SESSIONS_DIR` | `~/.agentone/var/sessions` | Django setting (`settings_local.py`) |
| `AGENTONE_ROOT` | `<repo>/.agentone` | Django setting |
| `AGENTONE_HOME` | `~/.agentone` | env |
| `AGENTONE_BROWSER_DIR` | `~/.agentone/var/browser` | env |

## Migration (`migrate_layout`)

`python3 manage.py migrate_layout` moves the pre-`var/` home containers into
`var/`, moves each scope's `sessions/` into `<scope>/var/sessions/`, and
re-keys install repos from `project_<name>` / `workspace_<name>` to
`projects/<pk>` / `workspaces/<pk>` (preserving `.git`, so stored tree SHAs
keep resolving). It is idempotent and supports `--dry-run`.

Path helpers in `runtime/paths.py` also read the legacy locations until the
new ones exist (sessions, browser profiles, install repos), so the upgrade
keeps working even if the command has not run yet.

## Backup

DB dump + `~/.agentone/{var/sessions,var/browser,secrets,projects,workspaces}/`
+ inline `.agentone/` manifest dirs. `var/install`, `var/cache`, and
`var/log` are re-creatable (install history is keyed by tree SHA but can be
rebuilt from the current manifests) and need no backup. Back up memory roots
if their contents need to be preserved.
