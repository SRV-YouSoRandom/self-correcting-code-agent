# Self-Correcting Code Sandbox Agent

An autonomous agent that takes a natural language prompt, writes Python code to fulfill it, executes that code in an isolated Docker sandbox, evaluates the result against a structured contract and an LLM-as-judge semantic check, and, if it fails, classifies the failure and automatically repairs the code, retrying until it succeeds or exhausts its budget.

Built to explore what "self-correcting" actually requires in practice: not just catching exceptions and retrying blindly, but classifying why something failed, choosing a repair strategy proportional to that failure, and bounding cost so the agent can't loop forever.

## What it does

Given a prompt like:

> "Write a script that generates a bar chart as a PNG file named chart.png, showing sales figures for 5 products, using matplotlib."

The agent:
1. **Plans**: asks an LLM to turn the prompt into a structured execution contract (expected artifacts, network requirements, timeout, success criteria)
2. **Generates**: asks an LLM to write a single-file Python script fulfilling that contract
3. **Executes**: runs the script inside an isolated, resource-limited Docker container with no network access by default
4. **Evaluates**: checks the result against three layers. Did it execute cleanly, does the output artifact structurally match the contract (right file type, size, columns, non-blank image, etc.), and does an LLM-as-judge agree the output actually satisfies the original intent
5. **Reflects**: if any layer failed, classifies the failure into one of seven categories, decides whether to patch the same approach or rethink it entirely, escalates to a stronger model if needed, and tries again, up to a bounded retry and token budget

The whole run is visible attempt-by-attempt in a Streamlit UI, including the exact code generated, stdout/stderr, evaluation reasoning, and error classification for each try.

## Demo

<img width="426" height="240" alt="Self Correcting Coding Sandbox Agent" src="https://github.com/user-attachments/assets/94b5534d-f388-4a8a-852c-cfca7f4d2c3f" />


## Architecture highlights

- **Framework-agnostic core.** All agent logic (planning, code generation, execution, evaluation, retry decisions) is implemented as pure functions operating on a single Pydantic state object. Two separate orchestrators, a hand-rolled Python state machine and a LangGraph adapter, run the exact same core logic. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full rationale.
- **Real sandbox isolation**, not a subprocess call. Every execution happens in a fresh, non-root, capability-dropped Docker container with hard memory/CPU/PID/file-descriptor limits, default-deny networking, and no host filesystem access. Verified with an adversarial security test suite (sandbox escape attempts, resource exhaustion, network bypass attempts).
- **Three-layer success evaluation**, because "the code ran without crashing" and "the code did what was asked" are different questions: execution layer (exit code, timeout), contract layer (structural checks on the output artifact, magic bytes, pixel variance for images, row/column checks for CSVs), and a semantic layer (LLM-as-judge against the original intent, fails closed on ambiguous responses).
- **A seven-category error taxonomy** (environment, syntax, runtime, resource, external, contract, semantic) that routes each failure to a proportional repair: a missing package gets patched with the same approach; a blocked scraper or a resource-exhausted process gets a fundamentally different approach on retry, not another attempt at the same thing.
- **Bounded everything.** Token budget, and a two-tier retry budget (patch attempts vs. rethink attempts) tracked independently, so a stubborn failure mode can't loop indefinitely or run up unbounded API cost.

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.12, managed with `uv` |
| LLM providers | OpenRouter and Google Gemini, behind a provider-agnostic client with model tiering (cheap/strong) |
| Sandbox | Docker, with a swappable runtime (`runc` by default; gVisor `runsc` supported via an environment variable, see [Known limitations](#known-limitations)) |
| Orchestration | A hand-rolled Python state machine and a LangGraph adapter, both running identical core logic |
| Persistence | SQLite, storing full session state as JSON |
| UI | Streamlit |
| Testing | pytest, with unit / integration / security suites |

## Project structure

```
src/agent/
├── core/            # framework-agnostic logic: state schema, node functions,
│                     # contract validation, error taxonomy, retry logic
├── llm/              # provider-agnostic LLM client (OpenRouter, Gemini) + prompts
├── sandbox/          # Docker-based isolated execution
├── orchestrators/     # plain Python state machine + LangGraph adapter
├── persistence/       # SQLite session storage
└── ui/                # Streamlit observability UI

tests/
├── unit/               # pure logic, no I/O
├── integration/         # real Docker + real LLM calls
├── security/            # adversarial sandbox/network/resource tests
└── fixtures/known_failure_gallery/  # real observed failure modes, as reusable prompts
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design rationale and a file-by-file breakdown.

## Setup

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Docker, with the daemon running and accessible from your shell
- An API key for at least one of: [OpenRouter](https://openrouter.ai/keys) (free models available, no card required) or [Google AI Studio / Gemini](https://aistudio.google.com/apikey) (free tier available)

### Install

```bash
git clone https://github.com/SRV-YouSoRandom/self-correcting-code-agent.git
cd self-correcting-code-agent
uv sync
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` and set:

```
OPENROUTER_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
LLM_PROVIDER=openrouter        # or "gemini"
OPENROUTER_MODEL_CHEAP=openrouter/free
OPENROUTER_MODEL_STRONG=openrouter/free
```

`openrouter/free` is a router model ID that automatically selects a working free model per request, no payment method required. If using Gemini instead, set `LLM_PROVIDER=gemini` and leave the model fields unset to use the defaults.

### Build the sandbox image

```bash
./scripts/build_sandbox_image.sh
```

### Run the UI

```bash
uv run streamlit run src/agent/ui/app.py
```

Open the local URL Streamlit prints, enter a task in the "New Run" tab, and watch it work.

### Run it headlessly (no UI)

```python
import asyncio
from agent.orchestrators.plain.runner import PlainOrchestrator

async def main():
    orchestrator = PlainOrchestrator()
    session = await orchestrator.run("Write a script that prints the first 10 Fibonacci numbers.")
    print(session.status, session.final_result)

asyncio.run(main())
```

## Testing

```bash
uv run pytest tests/unit/ -v                          # fast, no external dependencies
uv run pytest tests/integration/ -v -m integration     # requires Docker + real LLM calls, slower
uv run pytest tests/security/ -v -m security            # adversarial sandbox/network/resource tests
uv run pytest -v                                        # everything
```

## Known failure gallery

`tests/fixtures/known_failure_gallery/` contains real prompts, grounded in failures actually observed while building this project, organized by error category (environment, syntax, runtime, resource, external, contract, semantic). Useful both as test fixtures and as documentation of what the self-correction loop is actually built to handle.

## Known limitations

- **Network egress is bridge-or-nothing, not domain-restricted.** The execution contract captures an `allowed_domains` list, but true per-domain allowlisting requires an egress proxy in front of the sandbox, which isn't implemented yet. Today, a task that requires network access gets full outbound internet access, not a restricted allowlist.
- **gVisor is supported but not yet the default.** The sandbox runner accepts a `SANDBOX_RUNTIME` environment variable (e.g. `SANDBOX_RUNTIME=runsc`) to run containers under gVisor for stronger syscall-level isolation. It currently defaults to Docker's standard `runc` runtime; switching requires gVisor to be installed and registered as a Docker runtime on the host.
- **Free-tier LLM rate limits.** When using OpenRouter's free-tier models or Gemini's free tier, requests can hit provider rate limits (429/503/504) under heavy testing. The client retries transient errors with exponential backoff, but a sustained outage on the provider side can still exceed the retry window.
- **`openrouter/free` routes to a randomly selected underlying model per request**, so output quality and failure modes vary between runs. This is by design (it's what makes the free tier viable), but means results aren't perfectly reproducible run to run.

## License

MIT, see [LICENSE](./LICENSE).
