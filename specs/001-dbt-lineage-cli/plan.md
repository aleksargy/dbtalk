# Implementation Plan: dbtalk – Natural Language dbt Lineage Explorer

**Branch**: `001-dbt-lineage-cli` | **Date**: 2026-06-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-dbt-lineage-cli/spec.md`

## Summary

Build `dbtalk`, a Python 3.12 CLI tool that reads a dbt `manifest.json` and lets data
engineers ask natural language questions about model lineage, blast radius, and metadata.
The tool uses the Anthropic API with tool use to dispatch one of three graph/search
functions (`get_lineage`, `search_models`, `blast_radius`) and synthesises a plain-English
answer, rendered in the terminal via `rich`.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: anthropic, click, chromadb, pydantic, rich, networkx

**Storage**: ChromaDB ephemeral in-memory collection (rebuilt from manifest per invocation)

**Testing**: pytest with `tests/fixtures/manifest.json` (synthetic, ≥ 6 models; no network)

**Target Platform**: Docker (`python:3.12-slim` single-stage image); local venv for development

**Project Type**: CLI tool

**Performance Goals**: First visible output < 5s (excluding Anthropic API latency);
complete answer < 30s for manifests ≤ 500 models

**Constraints**: No network calls except Anthropic API; no `.sql` file parsing;
secrets via env vars only; `ANTHROPIC_API_KEY` from `os.environ`

**Scale/Scope**: Single-user interactive CLI; manifests up to ~500 models

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Manifest-Only Input | ✅ PASS | Only `manifest.json` is opened; zero `.sql` reads |
| II | Minimal Dependencies | ✅ PASS | `python-dotenv` (requested in plan args) is dropped; `os.environ` used instead |
| III | Separation of Concerns | ✅ PASS | 5 modules: manifest.py → embeddings.py → tools.py → agent.py → cli.py; downward-only imports enforced |
| IV | Secrets via Env Vars | ✅ PASS | `ANTHROPIC_API_KEY` from `os.environ`; `.env.example` committed (never real values) |
| V | Single CLI Entrypoint | ✅ PASS | Exactly one command: `dbtalk ask "<question>"` |
| VI | Docker Deployment | ✅ PASS | Single-stage `python:3.12-slim` Dockerfile at repo root |
| VII | Fixture-Based Testing | ✅ PASS | `tests/fixtures/manifest.json` synthetic manifest with 6 models; zero network calls |
| VIII | Data Engineer Readability | ✅ PASS | Function length ≤ 30 lines, plain-English names, type hints on all public functions |

**Complexity Tracking** — Principle II was the only potential violation:

| Violation | Resolution |
|-----------|------------|
| `python-dotenv` requested in plan args | Dropped. Users set `ANTHROPIC_API_KEY` via shell/Docker `--env`. README documents this. No amendment needed. |

## Project Structure

### Documentation (this feature)

```text
specs/001-dbt-lineage-cli/
├── plan.md              # This file
├── research.md          # Phase 0 output — all tech decisions documented
├── data-model.md        # Phase 1 output — Pydantic models + fixture spec
├── quickstart.md        # Phase 1 output — setup and usage guide
├── contracts/
│   └── cli.md           # Phase 1 output — CLI args, tool definitions, env vars
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/dbtalk/
├── __init__.py
├── manifest.py          # Reads + validates manifest.json → Pydantic models (DbtManifest)
├── embeddings.py        # Builds ChromaDB ephemeral collection from DbtManifest
├── tools.py             # get_lineage(), search_models(), blast_radius() pure functions
├── agent.py             # Anthropic API orchestration: tool dispatch + answer synthesis
└── cli.py               # Click entrypoint: `dbtalk ask "<question>" --manifest <path>`

tests/
├── fixtures/
│   └── manifest.json    # Synthetic manifest: 6 models, 3 sources, tests on 4 models
├── unit/
│   ├── test_manifest.py     # Parse + validate manifest; reject malformed JSON
│   ├── test_embeddings.py   # Build collection; search returns expected models
│   ├── test_tools.py        # get_lineage, blast_radius, search_models correctness
│   └── test_agent.py        # Tool dispatch logic (mock Anthropic client)
└── integration/
    └── test_cli.py          # Click test runner; end-to-end with mock Anthropic client

Dockerfile               # python:3.12-slim, single stage
pyproject.toml           # Entry point + approved deps + dev extras
.env.example             # Documents ANTHROPIC_API_KEY (no real values committed)
README.md                # Docker-first usage guide
```

**Structure Decision**: Single project. `src/dbtalk/` follows the constitution's
five-module hierarchy with strictly downward imports:
`cli → agent → tools → manifest / embeddings → manifest`.

## Phase 0: Research — Completed

See [research.md](research.md) for full decision log. Key decisions:

| Decision | Choice | Reason |
|----------|--------|--------|
| Manifest schema | dbt v12 (dbt Core ≥ 1.5) | Stable; includes `parent_map` + `child_map` |
| Embeddings | ChromaDB built-in ONNX model | No extra deps; bundled with `chromadb` |
| Anthropic model | `claude-haiku-4-5-20251001` | Fast + cheap for tool dispatch |
| Graph library | `networkx.DiGraph` | In approved list; `ancestors`/`descendants` built-in |
| Secrets | `os.environ` directly | `python-dotenv` not in approved deps |
| Layer classification | `fqn` path + name prefix heuristic | No dbt config field stores layer explicitly |
| ChromaDB mode | Ephemeral in-memory | Rebuilt per invocation; ≤ 2s for 500 models |

## Phase 1: Design — Completed

### Data Model

See [data-model.md](data-model.md) for full Pydantic schemas.

**Key types** (all in `src/dbtalk/manifest.py`):
- `DbtColumn` — name, description, data_type, tags, meta
- `DbtNode` — unique_id, name, resource_type, fqn, path, description, columns, depends_on, tags
- `DbtSource` — unique_id, name, source_name, description, columns, tags
- `DbtManifest` — metadata, nodes, sources, parent_map, child_map; `.models` and `.test_nodes` properties

**ChromaDB document schema** (in `src/dbtalk/embeddings.py`):
- One collection: `"dbt_models"`, ephemeral in-memory
- Document text: `"{name}: {description}. Columns: {col} ({col_desc}), ... Tags: {tags}."`
- Metadata: `unique_id`, `name`, `layer`, `has_tests` (bool), `tags`, `column_names`

**LineageGraph** (in `src/dbtalk/tools.py`):
- `networkx.DiGraph` where edges go parent → child
- Built from `manifest.parent_map`
- `nx.ancestors()` → upstream; `nx.descendants()` → blast radius

### CLI Contract

See [contracts/cli.md](contracts/cli.md) for full specification.

**Summary**:
- Command: `dbtalk ask "<question>" --manifest <path>`
- Exit codes: 0 (ok), 1 (user error), 2 (manifest error), 3 (API error)
- `ANTHROPIC_API_KEY` env var — only secret required
- Three Anthropic tools: `get_lineage`, `search_models`, `blast_radius`

### Tool Call Flow

```
cli.py
  └─ validates --manifest path + ANTHROPIC_API_KEY present
  └─ calls agent.run(question, manifest_path)
       └─ manifest.load(path) → DbtManifest
       └─ embeddings.build_collection(manifest) → ChromaDB collection
       └─ tools.build_graph(manifest) → nx.DiGraph
       └─ Anthropic API call #1: question + 3 tool definitions → tool_use block
       └─ dispatch to tools.get_lineage / tools.search_models / tools.blast_radius
       └─ Anthropic API call #2: tool result → text block (the answer)
  └─ rich.print(answer)
```

### Fixture Manifest Summary

`tests/fixtures/manifest.json` — 6 models, 3 sources, tests on 4 models.

| Model | Layer | Has Tests | PII Column |
|-------|-------|-----------|------------|
| stg_customers | staging | yes | email (tag: pii) |
| stg_orders | staging | **no** | — |
| stg_payments | staging | yes | — |
| int_orders | intermediate | yes | — |
| fct_revenue | marts | yes | — |
| fct_customers | marts | **no** | — |

Key test cases the fixture enables:
- "what does fct_revenue depend on?" → int_orders, stg_customers, raw_customers (source)
- "what breaks if I change stg_orders?" → int_orders, fct_revenue, fct_customers
- "find models with no tests" → stg_orders, fct_customers
- "find all models that reference PII columns" → stg_customers

### Quickstart

See [quickstart.md](quickstart.md) for setup steps (Docker + local venv).

### Agent Context Update

CLAUDE.md updated to reference this plan at
`specs/001-dbt-lineage-cli/plan.md`.
