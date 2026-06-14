# Quickstart: dbtalk

**Feature**: 001-dbt-lineage-cli
**Date**: 2026-06-14

---

## Prerequisites

- A `manifest.json` file produced by running `dbt docs generate` or `dbt compile`
  in your dbt project.
- An Anthropic API key (`ANTHROPIC_API_KEY`).

---

## Option A: Docker (Recommended)

```bash
# 1. Build the image
docker build -t dbtalk .

# 2. Run a question — mount your manifest and pass the API key
docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v /path/to/your/dbt/project/target:/manifest:ro \
  dbtalk ask "what does fct_revenue depend on?" --manifest /manifest/manifest.json
```

No Python installation required on the host machine.

---

## Option B: Local Development (venv)

```bash
# 1. Clone the repository
git clone <repo-url>
cd dbtalk

# 2. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows PowerShell

# 3. Install the package in editable mode
pip install -e ".[dev]"

# 4. Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 5. Run a question
dbtalk ask "what does fct_revenue depend on?" --manifest /path/to/manifest.json
```

---

## Example Questions

```bash
# Upstream lineage: what does a model depend on?
dbtalk ask "what does fct_revenue depend on?" --manifest ./target/manifest.json

# Blast radius: what downstream models are affected by a change?
dbtalk ask "what breaks if I change stg_orders?" --manifest ./target/manifest.json

# Source impact: which models read from a source?
dbtalk ask "which models touch the customers source?" --manifest ./target/manifest.json

# Governance: find models missing test coverage
dbtalk ask "find models with no tests" --manifest ./target/manifest.json

# Governance: find models with PII data
dbtalk ask "find all models that reference PII columns" --manifest ./target/manifest.json
```

---

## Running Tests

```bash
# Activate venv first (see Option B above)
pytest tests/
```

Tests use `tests/fixtures/manifest.json` — no real dbt project or API key required.

---

## Validation Checklist

- [ ] `ANTHROPIC_API_KEY` is set in the environment.
- [ ] The manifest file path is correct and the file exists.
- [ ] `dbtalk --help` prints the usage text without error.
- [ ] `dbtalk ask "find models with no tests" --manifest tests/fixtures/manifest.json`
  returns a list of model names without an API call error.

---

## Common Errors

| Error message | Cause | Fix |
|---------------|-------|-----|
| `ANTHROPIC_API_KEY environment variable is not set` | API key missing | `export ANTHROPIC_API_KEY="sk-ant-..."` |
| `manifest.json not found at <path>` | Wrong path | Check `--manifest` points to the right file |
| `Not a valid dbt manifest (missing required keys)` | Wrong JSON file | Run `dbt docs generate` first |
| `Anthropic API error: 401 Unauthorized` | Invalid API key | Check key value and permissions |
