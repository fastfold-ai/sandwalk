# Mux / concurrency integration probes

These are **opt-in live probes**, not CI. They hit a running Sandwalk agent
server and/or OpenRouter. They exist to separate three things that look the
same in the UI:

1. **Browser HTTP/1.1 connection cap** (split-view EventSources) — fixed by
   `GET /v1/events` mux (`capabilities.eventMux`).
2. **OpenRouter concurrency / rate limits** — this folder’s
   `openrouter_concurrent.py`.
3. **Sandwalk agent overhead** (system prompt, skills, tools, thread pool) —
   `sandwalk_mux_scale.py`.

OpenRouter’s public docs do not impose a “4 concurrent chats = 4× wait”
rule for paid keys. Free models are rate-limited; paid traffic is limited
per-key. See [OpenRouter quickstart](https://openrouter.ai/docs/quickstart)
and [FAQ — rate limits](https://openrouter.ai/docs/faq#how-are-rate-limits-calculated).

A live probe on a paid key (same prompt/model as the Sandwalk mux test)
showed **N=4 is allowed**, but not perfectly even: two streams matched the
~2s baseline TTFB, two waited ~8s. That is **not** the ~50s Sandwalk-4-chat
TTFB.

The ~50s stall was local: every chat rebuilt 186 LangChain tools and called
`Sandbox.load_datasets()` (six data-loader probes) on the GIL. After caching
native tool schemas and lazy dataset load, 4 parallel wraps are ~0s warm /
~0.4s cold. Restart `sandwalk serve` to pick this up, then re-run B.

## Prerequisites

- From `cli/`: `uv sync` so `httpx` is available.
- OpenRouter probe: `OPENROUTER_API_KEY` **or** `llm.openrouter_api_key` in
  `~/.sandwalk/config.json`.
- Sandwalk probe: agent server on `http://127.0.0.1:8787` (override with
  `SANDWALK_BASE_URL`), plus a backend API key from `sandwalk auth` if auth
  is enabled.

## Run

```bash
cd cli

# A. OpenRouter only — 1 stream then N concurrent streams (no Sandwalk)
uv run python tests/integration_mux/openrouter_concurrent.py
uv run python tests/integration_mux/openrouter_concurrent.py --n 4
# Same, but attach 80 dummy tools (closer to Sandwalk's native tool payload)
uv run python tests/integration_mux/openrouter_concurrent.py --n 4 --tools 80

# B. Sandwalk mux path — 1 chat then N chats on GET /v1/events
uv run python tests/integration_mux/sandwalk_mux_scale.py
uv run python tests/integration_mux/sandwalk_mux_scale.py --n 4
```

After a server restart, `[perf] deepagents …` lines land in
`~/.sandwalk/logs/agent-server.log` (model / tools / create_deep_agent /
first_stream spans).

Env knobs:

| Variable | Default | Meaning |
|----------|---------|---------|
| `OPENROUTER_MODEL` | `deepseek/deepseek-v4-flash` | Model slug |
| `OPENROUTER_CONCURRENCY` | `4` | Parallel OpenRouter streams (`--n` wins) |
| `SANDWALK_BASE_URL` | `http://127.0.0.1:8787` | Agent server |
| `SANDWALK_MUX_N` | `4` | Parallel Sandwalk chats (`--n` wins) |

## How to read the numbers

- **OpenRouter TTFB stays near the 1-stream baseline** when N=4 → the
  ~50s Sandwalk-4-chat delay is **not** an OpenRouter queue.
- **OpenRouter TTFB scales ~N×** → provider/key limit; check
  `https://openrouter.ai/api/v1/key` (printed as remaining/limit, never the
  secret).
- **Sandwalk 4-chat TTFB >> OpenRouter 4-stream TTFB** → agent setup or
  local serialization. Check `GET /v1/debug/health` (`thread_pool`,
  `active_runs`, `sse_streams_open`) while the probe runs.

Prompt is intentionally the same as the UI experiment:
`Hi, what skills do you have`. The OpenRouter path has **no** Sandwalk
tools, so completion is shorter; compare **TTFB**, not total tokens.
