# dbtalk

Ask natural language questions about your dbt project's lineage graph, right from the terminal.

```
dbtalk ask "what does fct_revenue depend on?" --manifest ./target/manifest.json
```

dbtalk reads the `manifest.json` of your dbt porject and uses Claude to answer questions about model dependencies, blast radius, and metadata. No database connection required or dbt installation required.

---

## Requirements

- A `manifest.json` from `dbt docs generate` or `dbt compile` (dbt Core ≥ 1.5, manifest schema v12)
- An [Anthropic API key](https://console.anthropic.com/)
- Docker (recommended) or Python 3.12+

---

## Quick Start

### Docker

```bash
docker build -t dbtalk .

docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v /path/to/your/dbt/project/target:/manifest:ro \
  dbtalk ask "what does fct_revenue depend on?" --manifest /manifest/manifest.json
```

### Local (venv)

```bash
python3.12 -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -e .

export ANTHROPIC_API_KEY="sk-ant-..."   # Windows: $env:ANTHROPIC_API_KEY = "sk-ant-..."

dbtalk ask "what does fct_revenue depend on?" --manifest ./target/manifest.json
```

---

## Usage

```
dbtalk ask "<question>" --manifest <path/to/manifest.json>
```

| Argument | Description |
|----------|-------------|
| `<question>` | Natural language question about your dbt project (required) |
| `--manifest` | Path to your `manifest.json` file (required) |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Missing API key or missing manifest file |
| `2` | Manifest is invalid or not a dbt manifest |
| `3` | Anthropic API error (network, rate limit, auth) |

---

## What You Can Ask

### Lineage: what does a model depend on?

```bash
dbtalk ask "what does fct_revenue depend on?" --manifest ./target/manifest.json
dbtalk ask "what are all the upstream sources for fct_customers?" --manifest ./target/manifest.json
dbtalk ask "which models touch the customers source?" --manifest ./target/manifest.json
```

### Blast radius: what breaks if I change something?

```bash
dbtalk ask "what breaks if I change stg_orders?" --manifest ./target/manifest.json
dbtalk ask "how many models depend on int_orders?" --manifest ./target/manifest.json
```

### Governance: find models missing tests or containing PII

```bash
dbtalk ask "find models with no tests" --manifest ./target/manifest.json
dbtalk ask "find all models that reference PII columns" --manifest ./target/manifest.json
dbtalk ask "which models have columns tagged as sensitive?" --manifest ./target/manifest.json
```

---

## How It Works

dbtalk passes your question to Claude along with three tools:

| Tool | What it does |
|------|-------------|
| `get_lineage` | Traverses the dependency graph upstream or downstream from a named model |
| `blast_radius` | Returns all downstream dependents recursively, grouped by dbt layer |
| `search_models` | Semantic search over model and column descriptions |

Claude decides which tool(s) to call, executes them against your manifest, and writes a plain-English answer citing model names.

```
manifest.json
     |
     v
manifest.py — parses JSON into typed Pydantic models
     |
     +---> tools.py — get_lineage / blast_radius (networkx graph traversal)
     |
     +---> embeddings.py — search_models (ChromaDB semantic search)
     |
     v
agent.py — Anthropic API + tool dispatch
     |
     v
cli.py — dbtalk ask (Click entrypoint)
```

dbtalk never reads `.sql` files. All information comes from `manifest.json`.

---

## Running Tests

The test suite uses a synthetic fixture manifest and a mock Anthropic client.

```bash
pip install -e ".[dev]"
pytest tests/
```

---

## Configuration

The only configuration dbtalk needs is an Anthropic API key, set as an environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

For Docker, pass it with `--env`:

```bash
docker run --rm -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY ...
```

The key is never written to disk or logged.

---

## Common Errors

| Error message | Fix |
|---------------|-----|
| `ANTHROPIC_API_KEY environment variable is not set` | `export ANTHROPIC_API_KEY="sk-ant-..."` |
| `manifest.json not found at <path>` | Check your `--manifest` path |
| `Not a valid dbt manifest` | Run `dbt docs generate` first; ensure dbt Core ≥ 1.5 |
| `API error: 401 Unauthorized` | Verify your API key is correct and active |
| `API error: 429 Too Many Requests` | You've hit the Anthropic rate limit; wait and retry |
