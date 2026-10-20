# Folder handling

Single source of truth for where AgentOne keeps things. Path logic lives in
`runtime/paths.py` — do not recompute `~/.agentone/...` paths elsewhere.

## Scopes (most-specific wins)

| Scope | Manifest dir | DB owner |
|---|---|---|
| `global` | `<repo>/.agentone/` (`settings.AGENTONE_ROOT`) | `parent_project=None` |
| `user` | `~/.agentone/{agents,skills,scripts,cronjobs}/` | `parent_project=None` (loads after global, user versions win) |
| `project` | `Project.agentone_dir` (legacy fallback `<path>/.agentone`) | `parent_project=<row>` |
| `workspace` | `Workspace.agentone_dir` (blank = bare path, no manifests) | parent project's namespace (`parent_project=workspace.parent_project`) |

User manifests use the same layout as global (`agents/<n>/agent.md`,
`skills/<s>/skill.md`, `scripts/`, `cronjobs/<n>.md`). Missing dirs are
skipped. Workspace manifests require `parent_project` to be set, otherwise
reload warns and skips.

## DB-canonical metadata (deprecated files)

- **No `project.md`, no `projects.yaml`, no `workspace.md`.**
  `Project` (`agentone_dir`, `storage`, `git_url/ref`, `main_workspace FK`)
  and `WorkspaceModel` (`parent_project FK`, `storage`, `agentone_dir`,
  `access`) are the source of truth, edited via UI/API. Existing rows were
  kept as-is; the new fields are nullable with legacy fallbacks.
- Leftover `project.md` / `projects.yaml` files on disk are
  **warn-and-ignore**: reload emits a `warning` details entry and never
  creates/updates rows from them. Safe to delete.
- Storage modes: project `inline_project | inline_workspace | central | git`,
  workspace `inline | central` (blank = unmanaged bare path).
  - inline workspace: `<workspace>/.agentone/` (creation offers `.gitignore`).
  - central: `~/.agentone/workspaces/<name>/` resp.
    `~/.agentone/projects/<name>/`.
  - git projects (future): row with `git_url/ref`, temp workspace on demand.

## Derived state under `~/.agentone/`

| Dir | Lifecycle |
|---|---|
| `sessions/<agent>/<pk>/` | Per-session scratch, lazy, `0700`. Location depends on scope (workspace/project/global agentone dir). Own=allow, other/base=deny. Archived kept forever; int-named orphans swept at startup only (`startup_cleanup`; recovery beat is disabled). |
| `runtime/<ver_pk>/` | Full tree extract per version + `.last_used`. GC after 1h idle, re-extracted on demand. |
| `install/global\|user\|project_<n>\|workspace_<n>/` | Git repos synced from scope source (`rsync --delete`), versioned by tree SHA. Re-syncable. |
| `upstream/*`, `staging/*` | Upstream clones + merged staging (upstream first, local overlays; `sources.yaml` + `skills.yaml` are config-only, excluded; staging uses `--delete`). Re-syncable. |
| `browser/` | Daemon token (`0600`), profiles, audit log. **Durable — back up.** Outside runtime GC. |
| `projects/<n>/`, `workspaces/<n>/` | Central manifest dirs (DB content). Back up with the DB. |

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
| `AGENTONE_SESSIONS_DIR` | `~/.agentone/sessions` | Django setting (`settings_local.py`) |
| `AGENTONE_ROOT` | `<repo>/.agentone` | Django setting |
| `AGENTONE_HOME` | `~/.agentone` | env |
| `AGENTONE_BROWSER_DIR` | `~/.agentone/browser` | env |

## Backup

DB dump + `~/.agentone/{sessions,browser,projects,workspaces}/` + inline
`.agentone/` manifest dirs. `install/upstream/staging/runtime` are
re-creatable and need no backup.
