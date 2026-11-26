# Model / provider routing

AgentOne separates **intent** (what a session is allowed to run on) from the
**current binding** (what actually served the last call).  This matters because
a provider switch must not mint a new immutable session version: settings are
copy-on-write, and re-pinning on every 429 would create dozens of versions and
throw away the context cache.

## Vocabulary

| Term | Meaning |
|---|---|
| `AiModel` | Provider-independent model facts (slug, rank, capabilities, star). |
| `AiModelOffering` | One provider serving that model (provider id, free/paid, health). Code often aliases this as `AiModel`. |
| `ApiKey` | A credential for that provider (budget, cooldown, sticky-key state). |
| `SessionRoute` | Mutable one-to-one row: current offering + key + attempt trace. |
| `SettingsModel` | Immutable intent: `local_only`, `route_pin`, `route_failover`, `route_target`, `route_wait_seconds`, `route_constraints`. |

## Pin levels and failover ladders

| `route_pin` | Binding | Default `route_failover` |
|---|---|---|
| `offering_key` | exact offering + key (tests/probes) | `none` |
| `offering` | exact provider + model | `keys` |
| `model` | canonical model, any provider | `providers` |
| `auto` | profile + constraints, resolve every call | `models` |

Failover is a ladder: `none` → `keys` → `providers` → `models`.  A session
never goes *down* a ladder it was not allowed to climb.  The chain is built by
`runtime.routing.build_chain` with a hard cap of 16 candidates and is ordered
by quality rank, free preference, live provider load and health, with the
current binding kept first for KV-cache friendliness.

## Profiles

Named `auto:*` profiles hide model choice behind constraints:

| Profile | Constraints | Wait |
|---|---|---|
| `auto:balanced` (default) | free preferred, tools, Strong+ | 10 s |
| `auto:best-free` | free only, tools, Strong+ | 10 s |
| `auto:best` | Excellent+, paid allowed, tools | 10 s |
| `auto:local` | local only, tools | 10 s |
| `auto:fast` | Capable+, least-loaded provider, tools | 5 s |
| `auto:reliable` | Strong+, tools, free preferred | 120 s |

Users pick a default profile in **Settings → Preferences → Default route**.
An explicit model choice in the composer overrides it for that session only.

## Agent defaults (`agent.md`)

Agents can set the same route intent in frontmatter.  These fields become an
immutable `SettingsModel` snapshot and inherit through `extends`:

```yaml
routePin: model                 # auto | model | offering | offering_key
routeFailover: providers        # none | keys | providers | models
routeTarget: auto:balanced      # or a canonical model name; omit to use `model:`
routeWaitSeconds: 10
routeConstraints:               # snake_case router keys
  require_tools: true
  min_tier: strong
  providers_allow: [groq]
localOnly: false
```

Precedence: explicit session pin/policy → agent values → inherited agent
values → user's default route profile.  Leaving `routeTarget` unset on an
`auto` pin is what lets the user's preference win.  Profile constraints never
narrow an explicit `model`/`offering` pin; use `routeConstraints` for that.
Full field reference and validation rules are in
[docs/manifest-format.md](manifest-format.md#routing-and-failover).

## Local-only scope policy

Projects, workspaces and sessions/agents can enable **Local only, no cloud**.
It is a scope-level guard, independent of the transient composer "Local" filter:

| Scope | Where it is set | Storage |
|---|---|---|
| Project | Project detail → Edit project | `Project.local_only` |
| Workspace | Workspace detail → Edit workspace | `WorkspaceModel.local_only` |
| Session | Chat → Settings → Behavior → "Local only (no cloud)" | `SettingsModel.local_only` (tri-state: unset / true / false) |
| Agent profile | `localOnly:` in `agent.md` (or admin/API on its `SettingsModel`) | `SettingsModel.local_only` |

`runtime.routing.scope_policy.effective_local_only()` ORs the session's own
setting, route constraint or `auto:local` target with the same fields on every
ancestor session, plus the session's workspace/project and each ancestor's
workspace/project.  The result is forced into `constraints["local_only"]`
**after** profile and explicit constraints are merged, so a `local_only: false`
route constraint cannot clear it.

Enforcement is on `AiModelOffering.is_cloud` (per offering), not
`ApiProvider.is_local`: a local provider may serve a cloud-suffixed model.
`build_chain` applies the guard even to strict `offering`/`offering_key` pins:
a cloud pin is rejected (or replaced by a local sibling when failover allows),
and the model-picker/default-model paths only select non-cloud offerings.
When no local route exists, the call fails with `no_candidate` rather than
silently reaching a cloud provider.  Direct LLM calls and provider smoke tests
started from a local-only session obey the same rule.

The policy is **additive**: descendants can tighten it, but a `false` value at
a narrower scope never clears a restriction from a wider scope.  Forked and
subsession chats inherit it through the parent-session chain even when they do
not carry the project or workspace foreign keys themselves.

## Wait vs failover

`route_wait_seconds` is the wall-clock budget for waiting on the *current*
target before moving down the ladder.  Workload defaults: chat 10 s,
background 120 s, smoke test 0 s.  `runtime.routing.decide_failure` classifies
an error before acting:

| Error | Decision |
|---|---|
| 429, short `Retry-After` inside budget | **wait** (park the call) |
| 429, quota/daily/monthly exhaustion | **fail over** (waiting cannot help) |
| 401/403, 404, config error | **fail over**; if ladder exhausted, surface |
| 503/timeout | short failover; if the whole chain fails, surface (or park for genuine 429) |
| 400 prompt/context | **raise** — switching providers burns quota on the same bad request |
| mid-stream failure | **raise** — partial output must never be duplicated |

`RateLimitError(wait=True)` is the admission-side signal from
`RateLimitChecker`: the key is on a short cooldown inside the budget, so the
call is parked rather than consuming a fallback candidate.  With a zero
budget (tests) the checker raises `ModelUnavailableError` immediately instead.

## Test isolation

`run_model_test` and `call_llm_direct` pin the exact offering *and* key with
`route_pin="offering_key"`, `route_failover="none"` and a zero wait budget.
A failure is therefore a verdict about that provider/key — never about a
sibling the router silently switched to.  The verdict records which key was
used.

## Favourites and quality tiers

`.agentone/models/favorites.yaml` holds the curated shortlist (matched by
slug, name or canonical id).  Stars are stored on `AiModel` with
`favorite_origin` so a catalog reload can remove a stale *curated* star but
never a star the user set in the UI (`favorite_origin="user"`).

Quality tiers are buckets over `leaderboard_rank`: Frontier ≤20, Excellent
≤60, Strong ≤150, Capable ≤350, Lightweight otherwise.  The UI shows tier
labels / 1–5 bars rather than raw ranks.  Composer picker filters:
favourites, free, local, all; Insights offers search and a "Favourites only"
toggle.

## Mid-chat switches

Changing the model in a session that already has messages injects a
`SYSTEM_NOTICE` with a context-handoff note.  The notice is skipped while a
query is `WAITING`/`ACTIVE` or the session has any live call, so the context is
never rewritten mid-stream and no chained turn can pick the note up as a fresh
request.  Provider failover does **not** inject a notice — it is an internal
repair, not a model change.

The notice is a direct conversation append (`Session._persist_message`), not an
inbound user message: it never goes through `add_user_message` /
`ingest_user_message` and never dispatches `process_turn`.  Switching models in
an idle session therefore does **not** start an LLM turn — the note only becomes
context for the next real user request.
