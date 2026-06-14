# CLI Contract: dbtalk

**Feature**: 001-dbt-lineage-cli
**Date**: 2026-06-14

---

## Command Interface

```
dbtalk ask "<question>" --manifest <path>
```

### Arguments

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `QUESTION` | string | yes | Natural language question about the dbt project |
| `--manifest` | path | yes | Path to the dbt `manifest.json` file |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — answer printed to stdout |
| 1 | User error — missing argument, missing env var, or invalid manifest path |
| 2 | Manifest error — file exists but is not a valid dbt manifest v12 |
| 3 | API error — Anthropic API call failed (network, auth, rate limit) |

---

## Examples

```bash
# Ask about upstream lineage
dbtalk ask "what does fct_revenue depend on?" --manifest ./target/manifest.json

# Ask about blast radius
dbtalk ask "what breaks if I change stg_orders?" --manifest ./target/manifest.json

# Ask about which models touch a source
dbtalk ask "which models touch the customers source?" --manifest ./target/manifest.json

# Find governance issues
dbtalk ask "find models with no tests" --manifest ./target/manifest.json
dbtalk ask "find all models that reference PII columns" --manifest ./target/manifest.json
```

---

## Standard Output Contract

**Normal output** (answer): written to **stdout** as plain text formatted with ANSI
colours via `rich`. Suitable for piping to a pager.

**Error output**: written to **stderr**. Never mixed with the answer on stdout.

**Progress indication**: a spinner (via `rich`) is shown on stderr while waiting for
the Anthropic API. Suppressed when stdout is not a TTY (i.e., when output is piped).

---

## Three LLM Tools (internal contract between agent.py and tools.py)

These are not user-facing CLI flags. They are the tool definitions passed to the
Anthropic API by `agent.py`, and the corresponding Python functions in `tools.py`.

### get_lineage

```json
{
  "name": "get_lineage",
  "description": "Traverse the dbt dependency graph upstream or downstream from a named model.",
  "input_schema": {
    "type": "object",
    "properties": {
      "model_name": {
        "type": "string",
        "description": "The short name of the dbt model (e.g. 'fct_revenue')"
      },
      "direction": {
        "type": "string",
        "enum": ["upstream", "downstream"],
        "description": "Traverse parents (upstream) or children (downstream)"
      },
      "depth": {
        "type": "integer",
        "description": "Maximum graph depth to traverse. 0 = unlimited.",
        "default": 0
      }
    },
    "required": ["model_name", "direction"]
  }
}
```

**Returns** (Python dict passed back to agent):
```python
{
  "model_name": "fct_revenue",
  "direction": "upstream",
  "depth": 0,
  "nodes": [
    {"unique_id": "model.jaffle_shop.int_orders", "name": "int_orders", "layer": "intermediate", "type": "model"},
    {"unique_id": "model.jaffle_shop.stg_customers", "name": "stg_customers", "layer": "staging", "type": "model"},
    {"unique_id": "source.jaffle_shop.jaffle_shop.raw_customers", "name": "raw_customers", "layer": "source", "type": "source"},
    ...
  ],
  "error": null  # or error message string if model not found
}
```

---

### search_models

```json
{
  "name": "search_models",
  "description": "Semantic search over model and column descriptions in the dbt project.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Natural language search query, e.g. 'models with PII columns' or 'models with no tests'"
      },
      "n_results": {
        "type": "integer",
        "description": "Maximum number of results to return.",
        "default": 10
      }
    },
    "required": ["query"]
  }
}
```

**Returns**:
```python
{
  "query": "models with PII columns",
  "results": [
    {
      "name": "stg_customers",
      "unique_id": "model.jaffle_shop.stg_customers",
      "description": "Staged customers from raw source data",
      "layer": "staging",
      "has_tests": true,
      "column_names": ["customer_id", "email", "name"],
      "tags": ["pii"],
      "distance": 0.12
    },
    ...
  ]
}
```

---

### blast_radius

```json
{
  "name": "blast_radius",
  "description": "Return all downstream dependents of a dbt model, grouped by dbt layer.",
  "input_schema": {
    "type": "object",
    "properties": {
      "model_name": {
        "type": "string",
        "description": "The short name of the dbt model to analyse (e.g. 'stg_orders')"
      }
    },
    "required": ["model_name"]
  }
}
```

**Returns**:
```python
{
  "model_name": "stg_orders",
  "total_affected": 3,
  "by_layer": {
    "intermediate": ["int_orders"],
    "marts": ["fct_revenue", "fct_customers"]
  },
  "error": null
}
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | yes | Anthropic API key. Set in shell or via Docker `--env`. |

No other environment variables are read. No `.env` file loading.

---

## Help Output

```
Usage: dbtalk ask [OPTIONS] QUESTION

  Ask a natural language question about your dbt project.

Options:
  --manifest PATH  Path to dbt manifest.json  [required]
  --help           Show this message and exit.
```
