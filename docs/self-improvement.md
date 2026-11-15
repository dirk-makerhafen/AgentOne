# Self-improvement loop

How a session's reflection becomes a behaviour change, a reusable capability,
or a fix to AgentOne itself — without letting an LLM edit its own harness.

The loop has three stages and one rule:

```
Evidence  →  Playbook  →  Change
(observations) (behaviour)  (skills / tools / scripts / harness)
```

**The reflection pass observes, the synthesizer proposes, the harness
bookkeeps, and a human or coding agent implements.** No stage applies its own
output automatically.

---

## 1. Evidence — the reflection report

At `session_end` (and before `compact_turn`) the `reflection-mixin` forks the
session and asks it to report raw observations: WHAT happened, WHY, and WHERE
a fix would go (`system_prompt`, `instructions`, `harness`, `tooling`,
`memory-knowledge`, `unclear`). That report is stored as a
`MessageType.REFLECTION` message and later persisted into the task's memory
node by `memory_walk(refresh=True)`.

The reflection prompt is deliberately observation-only. It must not draft
rules, design tools, or write code — that work happens downstream with access
to the codebase.

---

## 2. Playbook — behaviour

The memory synthesizer (`memory-manage`) consolidates reports into three
files per node. Two of them are structured:

| File | Schema | Purpose |
|---|---|---|
| `memory.md` | free markdown | Durable facts: what is true here |
| `reflection.md` | `agentone.playbook/1` | Behavioural rules: when X, do Y |
| `improvements.md` | `agentone.improvements/1` | Proposals bigger than a rule |

### `reflection.md` — the playbook

```markdown
---
schema: agentone.playbook/1
directives:
  - id: PB-1a2b3c4d
    fingerprint: stop-after-empty-dispatches
    rule: "Stop calling memory_merge after two consecutive empty dispatches."
    trigger: "running a memory tick"
    routing: prompt
    status: active
    support: 2
    evidence: [session:12355, session:23826]
    verification: "No memory_merge call follows an empty result."
---

Human-readable notes may follow. Only the frontmatter is injected.
```

| Field | Meaning |
|---|---|
| `id` | Stable identifier (`PB-…`). Generated from the fingerprint when absent |
| `fingerprint` | Identity of the lesson; repeated rewording merges into one directive |
| `rule` | The behaviour, one sentence |
| `trigger` | When the rule applies (used to phrase the injected line) |
| `routing` | Where the fix belongs — see the capability ladder below |
| `status` | `active`, `candidate`, or `retired` |
| `support` | How many observations back it (defaults to evidence count) |
| `evidence` | Session/report references, capped at 10 |
| `verification` | How to tell the rule worked |
| `capability` | Optional skill/tool/script name the rule points at |

The harness normalizes this file when a node is finalized:

- IDs and fingerprints are stabilized, so casing/punctuation changes do not
  create duplicates.
- Duplicates merge (max support, union of evidence).
- Status is clamped: `active` without any support becomes `candidate`; an
  unknown status becomes `candidate`; unknown routing becomes `prompt`.
- At most 40 directives per node, active first.
- **Malformed new-format frontmatter fails closed** — the node stays pending
  and is retried. Legacy plain-markdown `reflection.md` stays valid and is
  upgraded on its next synthesis.

### `improvements.md` — the change ledger

```markdown
---
schema: agentone.improvements/1
proposals:
  - id: IMP-4a2f1c90
    fingerprint: memory-merge-settings-override
    kind: harness
    scope: global
    status: candidate
    trigger: "memory_merge rejects settings_overrides"
    summary: "Transient failure is a harness bug, not an agent rule"
    detail: "spawn_subagent nests settings_overrides; pass access= instead."
    acceptance: "No agent workaround is recorded for this failure."
    evidence: [session:23826]
---
```

`kind` is `prompt`, `system_prompt`, `skill`, `tool`, `script`, or `harness`.
Proposals carry a spec and an acceptance check — never executable code, and
never an applied change. Identity is the summary, so adding detail or
evidence does not fork a proposal.

---

## 3. Change — the capability ladder

Choose the **lightest artifact that closes the gap**:

| Rung | Artifact | Use when | Where it lives |
|---|---|---|---|
| 1 | `memory.md` fact | The issue was missing knowledge | Memory node |
| 2 | Playbook directive | One-line behavioural correction | `reflection.md` |
| 3 | Skill | Multi-step procedure, checklist, templates, judgment | `skills/<name>/skill.md` |
| 4 | Tool | Deterministic, repeated operation with a stable contract | `scripts/` + `scripts.md` |
| 5 | Script | Code the agent runs with normal shell tools; no manifest needed | Any repo path or session folder |
| 6 | Harness fix | The platform itself is wrong (bug, missing guard, bad prompt plumbing) | This repository |

Routing rules:

- **Directive → skill** when the rule needs steps, examples, or templates.
  The directive stays short and points at the skill.
- **Skill → tool** when the procedure is fully deterministic and repeated.
  The skill then says "call tool X".
- **Tool → harness fix** when the tool exposes a platform bug rather than a
  missing capability.
- **Retire** a directive or skill when its failure signature disappears or
  `load_skill` usage stays at zero over a meaningful window. Keep the entry
  with `status: retired` so the same dead lesson is not re-added.

Scripts are a first-class rung: not every reusable piece of code needs to be a
formal tool. A script in the session folder or repository that the agent calls
with `execution.*` is often the right amount of structure. It still needs a
discoverable pointer (a playbook directive or a skill) or nobody will use it.

---

## 4. Consumption — what sessions actually see

`memoryPlaybook:` in `agent.md` (or the `memory_playbook` session setting)
pins one advisory message at session start, once per compaction segment:

```
[Memory playbook — advisory directives learned from earlier sessions ...]

**task (workspace AgentOne)**
- When running a memory tick: Stop after two consecutive empty dispatches.

**agent worker (workspace AgentOne)**
- When a tool call fails: inspect the error before retrying.

[Skills assigned to this agent — call load_skill("<name>") ...]
- memory-tick-cycle — Run a complete memory collection/synthesis cycle.
```

Resolution order is **task → agent → workspace → project → global**. All
layers contribute; identical fingerprints dedupe with the most specific source
winning. `retired` directives, `harness`-routed directives and
`memory`-routed directives are not injected — a harness bug must not become
an agent rule, and facts belong in `memory.md`.

Caps (`maxDirectives`, `maxChars`, `includeCandidates`, `includeSkills`,
`maxSkills`) are documented in
[manifest-format.md](manifest-format.md#memory-playbook). Enable it in
`baseagent`/the core agents; leave it off for the memory synthesizer itself so
synthesis is not biased by the playbook it is rewriting.

The skill half fixes an old discoverability gap: a generated skill is inert
unless the agent (a) has it in `skills:`, (b) has `skills.load_skill`, and
(c) is told it exists. The bootstrap message supplies (c); the manifest
supplies (a) and (b).

---

## 5. Filing work — `memory_improvements`

The synthesizer does not apply changes or create ready work. The explicit step
is a tool on `memory-manage`:

```python
memory_improvements(action="list")
memory_improvements(action="queue", kinds=["harness", "skill"])
```

When a full cycle is driven through `memory-manage` (walk → merge until nothing
remains), the agent is instructed to end it with one
`memory_improvements(action="queue")` call, so proposals do not sit unread in
memory files. `queue` files each proposal as a **backlog** `WorkItem` (deduped
by fingerprint marker). Backlog items do not dispatch; promoting one to
`ready`, assigning an agent, and verifying the result is a human decision.
Prompt edits are queued too — they still need a decision, and a backlog item is
the only durable reminder.

---

## 6. Verification and retirement

- **Directive:** does the failure signature recur in later reflections? If
  yes with the rule active, the rule is not working — rewrite or route it
  higher.
- **Skill:** `skill_assistant.skill_usage()` scans recent `load_skill` calls.
  A skill with no loads is dead weight; merge it back into a directive or
  retire it.
- **Tool/script:** the acceptance check in its proposal must be testable in
  the repository.
- **Harness:** the fix lands as code, with tests, and the workaround directive
  that motivated it is retired in the same change.

---

## 7. Operating notes

- Memory nodes are synthesized deepest-first (task → agent → scope), so a
  single pass moves one level. Run `memory_walk` + `memory_merge` until
  `remaining` is zero.
- `memory_finalize` (not the LLM) advances `.memory_sources.md`, and only
  after `finalize.py` validates and normalizes both structured files.
- Existing memory trees contain legacy prose `reflection.md` files. They stay
  valid, inject nothing, and acquire a playbook the next time their node is
  synthesized. No bulk conversion is performed — prose is not evidence.
- The playbook is advisory. It cannot add tools, change permissions, or
  override the user. The bootstrap header says so explicitly.

---

## See also

- [core-mechanisms.md](core-mechanisms.md) — dispatch pipeline and scheduler
- [manifest-format.md](manifest-format.md) — `memoryPlaybook`, `skills`,
  `scripts.md`
- [terminals.md](terminals.md) — the shell/terminal tools scripts run through
