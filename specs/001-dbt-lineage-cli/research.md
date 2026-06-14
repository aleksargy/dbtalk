# Research: dbtalk – Natural Language dbt Lineage Explorer

**Feature**: 001-dbt-lineage-cli
**Date**: 2026-06-14
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## Decision 1: dbt Manifest Schema Version

**Decision**: Target dbt manifest schema v12 (dbt Core ≥ 1.5).

**Rationale**: v12 is the current stable schema as of dbt Core 1.7. It includes
`parent_map`, `child_map`, `nodes`, and `sources` at the top level — exactly what
we need. Older versions (v9–v11) lack `child_map` or have different node structures.
Requiring v12 covers the vast majority of active dbt projects (1.5+ released 2023-07).

**Alternatives considered**:
- Support v9–v11 via schema migration: rejected — adds complexity with no benefit
  for new projects.
- Parse raw SQL as fallback: rejected — violates Principle I of the constitution.

**Key fields used from manifest**:
- `metadata.dbt_schema_version` — schema validation
- `nodes` — models (`resource_type = "model"`), tests (`resource_type = "test"`),
  seeds, snapshots
- `sources` — source table declarations
- `parent_map` — node_id → [upstream_node_ids] (for `get_lineage` upstream)
- `child_map` — node_id → [downstream_node_ids] (for `get_lineage` downstream and
  `blast_radius`)
- Per-node: `name`, `description`, `columns`, `tags`, `fqn`, `path`, `depends_on`
- Per-column: `name`, `description`, `data_type`, `tags`, `meta`

---

## Decision 2: Semantic Embedding Strategy

**Decision**: Use ChromaDB's built-in default embedding function
(`chromadb.utils.embedding_functions.DefaultEmbeddingFunction`), which uses a
lightweight ONNX model bundled with the `chromadb` package.

**Rationale**: No extra dependencies required — the ONNX runtime and embedding model
are distributed with `chromadb`. Anthropic does not offer a standalone embeddings API
endpoint, so using the Anthropic SDK for embeddings is not possible. The built-in model
(all-MiniLM-L6-v2 via ONNX) produces sentence embeddings of sufficient quality for
short model and column descriptions.

**Alternatives considered**:
- OpenAI embeddings: rejected — would require `openai` package (violates Principle II)
  and an additional API key.
- Manual TF-IDF: rejected — poor semantic recall for natural language queries like
  "find models with PII columns".
- Sentence-transformers directly: rejected — separate heavy dependency
  (violates Principle II); already included inside chromadb via ONNX.

**Embedding document format** (per model):
```
{model_name}: {description}. Columns: {col1} ({col1_desc}), {col2} ({col2_desc}).
Tags: {tags}. Path: {fqn}.
```

**Collection strategy**: Ephemeral in-memory ChromaDB client (`chromadb.Client()`)
rebuilt from the manifest on each invocation. No persistence. For manifests ≤ 500 models,
rebuild time is < 2 seconds. If performance becomes an issue, a persistent client
can be introduced via a constitution amendment.

---

## Decision 3: Anthropic API Model and Tool Use Pattern

**Decision**: Use `claude-haiku-4-5-20251001` as the default model for tool selection
and answer synthesis. Expose three tools via the Anthropic tool use API.

**Rationale**: Haiku is fast and cheap for structured tool dispatch, and the questions
are well-constrained. The tool use loop terminates after the agent calls a tool and
receives its result — no multi-turn looping needed for the initial version.

**Tool use flow**:
1. `agent.py` sends the user's question + three tool definitions to the Anthropic API.
2. The API returns a `tool_use` block naming one tool and its arguments.
3. `agent.py` dispatches to the matching function in `tools.py` and gets the result.
4. `agent.py` sends the tool result back to the API in a follow-up call.
5. The API returns the final plain-English answer in a `text` block.
6. `cli.py` renders the answer via `rich`.

**Alternatives considered**:
- `claude-sonnet-4-6`: better reasoning but ~10× slower and more expensive for a
  tool-dispatch task where the structure is already defined.
- Multi-turn agentic loop: rejected for v1 — the three tools cover all use cases
  without requiring chained calls; adds latency and token cost.

**Tool definitions**:
```
get_lineage(model_name: str, direction: "upstream"|"downstream", depth: int = 3)
  → list of model names with their layer (staging/intermediate/marts)

search_models(query: str)
  → list of (model_name, description, relevance_score) tuples

blast_radius(model_name: str)
  → dict of {layer: [model_names]} for all downstream dependents
```

---

## Decision 4: Graph Traversal Library

**Decision**: Use `networkx.DiGraph` for the lineage graph.

**Rationale**: `networkx` is in the approved dependency list and provides BFS/DFS
traversal, ancestor/descendant queries, and weakly-connected-component analysis out of
the box. Building a custom graph traversal is unnecessary complexity.

**Graph construction**: Build the DiGraph from `parent_map` during manifest parsing.
Nodes are unique_ids; edges go from parent → child (downstream direction).
`networkx.ancestors(G, node)` gives upstream; `networkx.descendants(G, node)` gives
the full blast radius.

**Depth-limiting**: Use `nx.bfs_tree(G, node, depth_limit=depth)` for `get_lineage`
when a depth is specified.

---

## Decision 5: Secrets and Configuration

**Decision**: Read `ANTHROPIC_API_KEY` from `os.environ` directly. No `.env` file
loading library.

**Rationale**: `python-dotenv` is NOT in the approved dependency list (Principle II).
Docker's `--env` and `--env-file` flags, plus standard shell `export`, are sufficient
for all deployment scenarios. Users running locally MUST set the env var in their shell
before invoking the tool.

**Error handling**: If `ANTHROPIC_API_KEY` is missing, `cli.py` MUST print a clear
message — "ANTHROPIC_API_KEY environment variable is not set" — and exit with code 1
before making any API call.

---

## Decision 6: CLI Framework

**Decision**: Use `click` with a single `ask` command group.

**Rationale**: `click` is in the approved dependency list. The CLI surface is minimal
(`dbtalk ask "<question>" --manifest <path>`), so no complex routing is needed.
`click` handles argument parsing, help text generation, and error reporting cleanly.

**Entry point** (in `pyproject.toml`):
```toml
[project.scripts]
dbtalk = "dbtalk.cli:cli"
```

---

## Decision 7: Layer Classification

**Decision**: Classify a model's dbt layer by inspecting its `fqn` path (list of
folder components) or name prefix:
- Path contains "staging" or name starts with "stg_" → staging
- Path contains "intermediate" or name starts with "int_" → intermediate
- Path contains "marts" or name starts with "fct_" or "dim_" → marts
- Otherwise → "other"

**Rationale**: dbt projects commonly follow the `stg_` / `int_` / `fct_` / `dim_`
naming convention. The `fqn` field in the manifest contains the folder path, which
provides a reliable fallback. No dbt config field explicitly stores the layer.

**Alternatives considered**:
- Using dbt's `config.schema` field: unreliable — projects configure this differently.
- Requiring the user to tag models: rejected — adds friction for existing projects.

---

## Resolved Clarifications

All technical decisions above were derived from:
1. The project constitution (approved dependency list, Principle constraints)
2. The user's explicit stack specification in the `/speckit-plan` arguments
3. dbt manifest v12 documentation
4. ChromaDB and Anthropic SDK documentation

No NEEDS CLARIFICATION markers remain.
