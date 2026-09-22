# Architecture

This document explains the design decisions behind the Self-Correcting Code Sandbox Agent — why the core logic is framework-agnostic, how the self-correction loop actually decides what to do on failure, and how the pieces fit together. For setup and usage, see [`README.md`](./README.md).

## Design goal: framework-agnostic core

A common way to build an agent loop is to pick an orchestration framework (LangGraph, AutoGen, CrewAI) and write the logic directly inside its abstractions. This project deliberately does the opposite: the core logic is written as plain, framework-agnostic Python first, and orchestration frameworks are adapters on top of it, not the foundation underneath it.

Concretely, this means every step of the agent loop — `plan`, `generate`, `execute`, `evaluate`, `reflect` — is a pure function with the same shape:

```python
async def node_name(session: SessionState, *dependencies) -> SessionState:
    ...
    return session
```

Each function takes the current session state, does its work (usually an LLM call or a sandbox execution), mutates the state, and returns it. None of these functions know or care what's calling them.

On top of these five functions sit two separate orchestrators:

- **`orchestrators/plain/runner.py`** — a hand-rolled `while` loop that reads `session.status` and dispatches to the matching node function. About 50 lines, no framework dependency beyond the node functions themselves.
- **`orchestrators/langgraph/graph.py`** — the exact same five node functions, wired into a LangGraph `StateGraph` with conditional edges based on `session.status`.

Both orchestrators are independently tested (`tests/integration/test_orchestrator_plain.py`, and cross-checked in `tests/integration/test_orchestrators_parity.py`), and both produce a `SessionState` with an identical field structure — verified directly by a parity test that compares `model_dump().keys()` between a plain-run session and a LangGraph-run session on the same prompt.

The payoff: adding a third orchestrator (say, a different framework, or a distributed/queue-based runner for production) means writing a new dispatcher over the same five functions — not re-implementing the agent's actual reasoning.

## The self-correction loop
    ┌─────────┐
    │  PLAN   │  LLM turns prompt into a structured ExecutionContract
    └────┬────┘
         ▼
    ┌─────────┐
    │GENERATE │  LLM writes a single-file Python script for the contract
    └────┬────┘
         ▼
    ┌─────────┐
    │ EXECUTE │  Script runs in an isolated Docker container
    └────┬────┘
         ▼
    ┌─────────┐
    │EVALUATE │  Three-layer check: execution → contract → semantic
    └────┬────┘
         │
  passed │ failed
  ┌──────┴──────┐
  ▼             ▼

SUCCEEDED ┌─────────┐
│ REFLECT │ Classify failure, decide patch/rethink, check budget
└────┬────┘
│
budget OK │ budget exhausted
┌──────────┴──────────┐
▼ ▼
back to GENERATE ABORTED_BUDGET


### Plan

The Plan step doesn't just interpret the prompt — it produces a structured **execution contract** (`core/contract/schema.py`): what artifact(s) the code should produce, what type they should be, minimum size/row/column expectations, whether network access is needed, a timeout, and a plain-language success criterion. This contract is what makes the later Evaluate step possible to do programmatically rather than by re-asking an LLM "did this work?" every time.

### Generate

Straightforward: given the prompt and the contract, produce a single-file Python script. Code fences get stripped (`strip_code_fences`), and the result is stored on the session as `current_code`.

### Execute

The generated code runs inside a fresh, isolated Docker container (see [Sandbox isolation](#sandbox-isolation) below). This step is the only synchronous node in the pipeline — it doesn't call an LLM, so no `async`/`await` is needed here, unlike every other node.

### Evaluate — three layers

A script that runs without crashing is not the same as a script that did what was asked. Evaluation happens in three layers, and the first one that fails stops the check there (no point running a semantic judge on code that never produced a valid CSV):

1. **Execution layer** (`validate_execution_layer`) — did the process exit cleanly and not time out?
2. **Contract layer** (`validate_contract_layer`) — does the artifact structurally match the contract? Magic-byte checks for images, pixel-variance checks to catch blank/near-blank charts, row/column checks for CSVs, non-empty checks for JSON.
3. **Semantic layer** (`judge_semantic_success`) — an LLM is shown the original prompt, the contract's success criteria, and a summary of the output, and asked to judge whether it actually fulfills the intent. This is the only layer that can catch "the code ran and produced a file, but it's the wrong data" — something no amount of structural checking alone can catch. If the judge's response can't be parsed as valid JSON, the result is `passed=False`, not a silent pass — failing closed rather than open.

### Reflect — classification and repair routing

When evaluation fails, Reflect does four things in sequence:

1. **Classify** the failure. If it failed at the contract layer, `classify_contract_failure`. If semantic, `classify_semantic_failure`. Otherwise, the execution result's traceback is parsed (`errors/traceback_parser.py`) and mapped to one of seven categories (`errors/taxonomy.py`) — see the table below.
2. **Decide a repair strategy.** Each category maps to either `patch` (fix the specific problem, keep the approach) or `rethink` (the approach itself needs to change). `retry/router.py` also decides which model tier to use: rethink-tier repairs always use the strong model; patch-tier repairs start on the cheap model and escalate to strong after `ESCALATION_THRESHOLD` (2) failed patches.
3. **Check budget.** Two independent budgets are tracked on the session: a token budget (hard cap on cumulative prompt+completion tokens) and a two-tier retry budget (separate caps for patch attempts and rethink attempts, so exhausting one doesn't block the other). If either is exhausted, the session terminates as `ABORTED_BUDGET` with a clear reason, rather than looping.
4. **Build the repair prompt and retry.** Using a bounded history of past attempt summaries (`context/attempt_log.py`, capped at 10, older entries collapsed into a single "N earlier attempts omitted" line) plus full detail of the most recent failure, a patch or rethink prompt template is filled in and sent to the LLM. The resulting code becomes the next `GENERATE`'s output, and the loop returns to `EXECUTING`.

### Error taxonomy

| Category | Example | Repair strategy | Why |
|---|---|---|---|
| `environment` | `ModuleNotFoundError`, missing file | patch | Usually a single import/dependency fix |
| `syntax` | `SyntaxError`, `IndentationError` | patch | Straightforward regeneration |
| `runtime` | `TypeError`, `KeyError`, `IndexError` | patch | Logic bug in an otherwise sound approach |
| `resource` | timeout, `MemoryError` | rethink | The approach itself is too expensive; patching won't fix an O(n²) algorithm |
| `external` | HTTP 403/429, connection errors | rethink | Retrying the identical request usually fails the same way |
| `contract` | artifact too small, missing columns | patch | Approach is usually right, output just needs adjustment |
| `semantic` | LLM-as-judge disagrees, or judge response unparseable | rethink | Code executed fine; the *approach* didn't satisfy intent |

## Sandbox isolation

Every execution happens in a fresh Docker container, destroyed immediately after (`sandbox/runner.py`). No container is reused across retries, which also means no state — including any host access a hostile script might have found — persists between attempts.

Isolation measures, verified by `tests/security/`:

- **No root.** The image runs as a non-root user (`sandbox`, uid 1000) baked in at build time.
- **All Linux capabilities dropped** (`cap_drop=["ALL"]`), plus `no-new-privileges`.
- **Resource limits enforced by the container runtime, not trusted to the script**: memory cap, CPU cap (`nano_cpus`), process count cap (`pids_limit`), and a file-descriptor `ulimit` (added after adversarial testing found scripts could otherwise open unbounded file handles — see `test_excessive_file_descriptors_are_limited`).
- **Wall-clock timeout enforced by the orchestrator**, polling the container from outside rather than trusting the process to respect a timeout itself — this catches genuinely hostile code (infinite loops, fork bombs) that wouldn't self-terminate.
- **Network is default-deny.** Unless the contract explicitly sets `requires_network=True`, the container gets `network_mode="none"` — no DNS resolution, no outbound connections, no access to the cloud metadata endpoint (`169.254.169.254`) or localhost. Verified directly in `test_network_isolation.py`.
- **Filesystem isolation via bind mount**, not `docker cp` — each run gets a fresh temp workspace bind-mounted to `/workspace`, deleted after the run. The script has no path to anything outside it.

### Current limitation: network is bridge-or-nothing

When a task does need network access, the container currently gets full outbound internet access (`network_mode="bridge"`), not a domain-restricted allowlist. The execution contract already captures an `allowed_domains` field, but enforcing it would require an egress proxy sitting in front of the container — not yet implemented. This is a known, documented gap, not an oversight; see `README.md`'s Known Limitations section.

### gVisor

The sandbox runner reads a `SANDBOX_RUNTIME` environment variable and passes it straight through to Docker's `runtime=` container option. Setting `SANDBOX_RUNTIME=runsc` (with gVisor installed and registered as a Docker runtime on the host) switches every container to gVisor's userspace-kernel syscall interception with zero code changes — this is a deliberate extension point, not a partially-built feature.

## Data model

Everything flows through one Pydantic object, `SessionState` (`core/state.py`):

- `contract: ExecutionContract` — what the Plan step decided success looks like
- `current_code: str` — the code currently being executed
- `attempts: list[AttemptRecord]` — one entry per execution, each carrying its own code, execution result, evaluation result, and error classification
- `token_budget` / `retry_budget` — the two independent budget trackers described above
- `status: SessionStatus` — the state machine's current position, which both orchestrators read to decide what to run next

This single-object design is what makes the framework-agnostic core possible: LangGraph is happy to use an arbitrary object (not just a `TypedDict`) as its graph state as long as nodes return an updated instance, and a hand-rolled loop needs nothing more than "read a field, call a function." Neither orchestrator needs its own parallel state representation.

## Persistence

`persistence/db.py` stores each session as a single SQLite row: a few indexed columns (`session_id`, `status`, timestamps) for querying, and the full `SessionState` serialized to JSON in one column. This is a deliberate simplicity trade-off — one file always round-trips perfectly through Pydantic, at the cost of not being able to write SQL queries against individual attempts. Given the project's scope, that trade favors simplicity; a normalized schema would be the right call if this needed to support cross-session analytics at scale.

Every orchestrator step saves the session after it runs, not just at the end — so a session that crashes mid-loop can be inspected via `load_session(session_id)` up to its last completed step, and the Streamlit UI's Session History tab reads directly from this store.

## Observability UI

The Streamlit UI (`ui/`) is a thin rendering layer over `SessionState` — it doesn't know or care whether a session came from a live run or was loaded from SQLite; `trace_view.py`'s rendering functions work identically either way. Failed attempts auto-expand in the trace view, successful ones stay collapsed, so a reviewer scanning a run sees the interesting recovery attempts first without clicking through everything.

## Testing strategy

- **`tests/unit/`** — pure logic, no Docker, no LLM calls, runs in well under a second. Covers the error classifier, contract validators, retry router, attempt log, and state model invariants (like `RetryBudget`'s patch/rethink independence).
- **`tests/integration/`** — real Docker containers and real LLM calls. Covers actual sandbox behavior (timeouts, network blocking, workspace isolation between attempts) and full orchestrator runs, including a dedicated parity test asserting both orchestrators produce structurally equivalent `SessionState` output on the same prompt.
- **`tests/security/`** — adversarial tests that deliberately try to break the sandbox: read host files, access the Docker socket, escalate to root, exhaust memory/CPU/PIDs/file descriptors, bypass network isolation to reach the cloud metadata endpoint or localhost. This suite actually found and fixed a real gap during development — no file-descriptor `ulimit` had been set, so a script could open unbounded file handles; the security test caught it, and the fix now ships with a regression test locked in.
- **`tests/fixtures/known_failure_gallery/`** — not hypothetical test data. Every entry is grounded in a failure actually observed while building this project (a real contract-layer size failure, a real LLM-as-judge JSON-parse failure, a real syntax error from a free-tier model), organized by the same seven-category taxonomy used in production.
