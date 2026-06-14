# Data Model: dbtalk – Natural Language dbt Lineage Explorer

**Feature**: 001-dbt-lineage-cli
**Date**: 2026-06-14

---

## Overview

All Pydantic models live in `src/dbtalk/manifest.py`. They map directly to the fields
that `dbtalk` reads from `manifest.json` — no fields are derived from SQL files.
Unknown fields in the manifest are silently ignored (use `model_config = {"extra": "ignore"}`).

---

## Pydantic Models

### DbtColumn

```python
class DbtColumn(BaseModel):
    name: str
    description: str = ""
    data_type: str = ""
    tags: list[str] = []
    meta: dict = {}
```

Represents a single column within a model or source node. The `tags` field is used
to detect PII and other governance labels.

---

### DbtNodeDependsOn

```python
class DbtNodeDependsOn(BaseModel):
    nodes: list[str] = []
```

Holds the list of `unique_id` strings that a node directly depends on. Parsed from
`nodes[*].depends_on` in the manifest.

---

### DbtNode

```python
class DbtNode(BaseModel):
    unique_id: str
    name: str
    resource_type: str          # "model", "test", "seed", "snapshot", etc.
    package_name: str = ""
    fqn: list[str] = []         # folder path components, e.g. ["jaffle_shop", "staging", "stg_customers"]
    path: str = ""              # relative .sql path, e.g. "staging/stg_customers.sql"
    description: str = ""
    columns: dict[str, DbtColumn] = {}
    depends_on: DbtNodeDependsOn = DbtNodeDependsOn()
    tags: list[str] = []
    config: dict = {}
```

Represents any node in the manifest's `nodes` dict. `dbtalk` primarily operates on
nodes where `resource_type == "model"`. Test nodes (`resource_type == "test"`) are
used only to determine test coverage status.

---

### DbtSource

```python
class DbtSource(BaseModel):
    unique_id: str
    name: str                   # table name, e.g. "raw_customers"
    source_name: str = ""       # source group name, e.g. "jaffle_shop"
    resource_type: str = "source"
    description: str = ""
    columns: dict[str, DbtColumn] = {}
    tags: list[str] = []
```

Represents a source table declared in the manifest's `sources` dict.

---

### ManifestMetadata

```python
class ManifestMetadata(BaseModel):
    dbt_schema_version: str = ""
    dbt_version: str = ""
    generated_at: str = ""
```

Top-level manifest metadata. `dbt_schema_version` is checked during validation to
ensure the manifest is v12 or later.

---

### DbtManifest

```python
class DbtManifest(BaseModel):
    metadata: ManifestMetadata = ManifestMetadata()
    nodes: dict[str, DbtNode] = {}
    sources: dict[str, DbtSource] = {}
    parent_map: dict[str, list[str]] = {}   # node_id → [upstream_node_ids]
    child_map: dict[str, list[str]] = {}    # node_id → [downstream_node_ids]

    @property
    def models(self) -> dict[str, DbtNode]:
        """Return only model nodes (resource_type == 'model')."""
        return {k: v for k, v in self.nodes.items() if v.resource_type == "model"}

    @property
    def test_nodes(self) -> dict[str, DbtNode]:
        """Return only test nodes (resource_type == 'test')."""
        return {k: v for k, v in self.nodes.items() if v.resource_type == "test"}
```

The top-level parsed manifest. `parent_map` and `child_map` are used directly to
build the `LineageGraph` without re-parsing `depends_on` fields.

---

## LineageGraph

Lives in `src/dbtalk/tools.py` as a plain function that builds and caches a
`networkx.DiGraph`:

```python
# Node IDs are unique_ids (e.g. "model.jaffle_shop.stg_customers")
# Edges go parent → child (upstream → downstream)
# Built once from manifest.parent_map and reused across tool calls
```

**Graph operations used**:

| Operation | networkx call | Used by |
|-----------|--------------|---------|
| All upstream ancestors | `nx.ancestors(G, node_id)` | `get_lineage(..., direction="upstream")` |
| Upstream to depth N | `nx.bfs_tree(G.reverse(), node_id, depth_limit=N)` | `get_lineage` with depth |
| All downstream descendants | `nx.descendants(G, node_id)` | `blast_radius` |
| Downstream to depth N | `nx.bfs_tree(G, node_id, depth_limit=N)` | `get_lineage(..., direction="downstream")` |

---

## ChromaDB Collection Schema

Built in `src/dbtalk/embeddings.py`. One collection named `"dbt_models"`.

**Document per model**:
```
{model_name}: {description}. Columns: {col_name} ({col_desc}), ... Tags: {tags}. Path: {fqn_path}.
```

**Metadata per document**:
```json
{
  "unique_id": "model.jaffle_shop.stg_customers",
  "name": "stg_customers",
  "layer": "staging",
  "has_tests": true,
  "tags": "pii,finance",
  "column_names": "customer_id,email,name"
}
```

Metadata is used for filtering (e.g., `where={"has_tests": False}`) without needing
to re-embed or re-query for simple boolean checks.

---

## Fixture Manifest Structure

`tests/fixtures/manifest.json` — synthetic manifest for testing.

**Models (6 total)**:

| unique_id | name | layer | upstream | has_tests | PII columns |
|-----------|------|-------|----------|-----------|-------------|
| `model.jaffle_shop.stg_customers` | stg_customers | staging | raw_customers (source) | yes (not_null on customer_id) | email |
| `model.jaffle_shop.stg_orders` | stg_orders | staging | raw_orders (source) | **no** | — |
| `model.jaffle_shop.stg_payments` | stg_payments | staging | raw_payments (source) | yes (not_null on payment_id) | — |
| `model.jaffle_shop.int_orders` | int_orders | intermediate | stg_orders, stg_payments | yes | — |
| `model.jaffle_shop.fct_revenue` | fct_revenue | marts | int_orders, stg_customers | yes | — |
| `model.jaffle_shop.fct_customers` | fct_customers | marts | stg_customers, int_orders | **no** | — |

**Sources (3 total)**:

| unique_id | source_name | name |
|-----------|-------------|------|
| `source.jaffle_shop.jaffle_shop.raw_customers` | jaffle_shop | raw_customers |
| `source.jaffle_shop.jaffle_shop.raw_orders` | jaffle_shop | raw_orders |
| `source.jaffle_shop.jaffle_shop.raw_payments` | jaffle_shop | raw_payments |

**Test coverage summary for fixture**:
- Models with NO tests: `stg_orders`, `fct_customers`
- Models with PII columns: `stg_customers` (email column tagged "pii")

**Lineage for key test cases**:
- Upstream of `fct_revenue`: `int_orders` → `stg_orders`, `stg_payments`; `stg_customers` → `raw_customers`
- Blast radius of `stg_orders`: `int_orders` → `fct_revenue`, `fct_customers`
- Models touching `raw_customers` source: `stg_customers` → `fct_revenue`, `fct_customers`
