from __future__ import annotations

import networkx as nx

from dbtalk.manifest import DbtManifest, DbtNode


def build_graph(manifest: DbtManifest) -> nx.DiGraph:
    """Build a directed graph where edges go parent → child (upstream → downstream)."""
    graph = nx.DiGraph()

    for unique_id, node in manifest.nodes.items():
        graph.add_node(unique_id, name=node.name, resource_type=node.resource_type)
    for unique_id, source in manifest.sources.items():
        graph.add_node(unique_id, name=source.name, resource_type="source")

    # parent_map: child_id → [parent_ids], so edge is parent → child
    for child_id, parent_ids in manifest.parent_map.items():
        for parent_id in parent_ids:
            if parent_id in graph and child_id in graph:
                graph.add_edge(parent_id, child_id)

    return graph


def classify_layer(fqn: list[str], name: str) -> str:
    """Classify a model into a dbt layer based on its fqn path or name prefix."""
    fqn_path = "/".join(fqn).lower()
    name_lower = name.lower()
    if "staging" in fqn_path or name_lower.startswith("stg_"):
        return "staging"
    if "intermediate" in fqn_path or name_lower.startswith("int_"):
        return "intermediate"
    if "marts" in fqn_path or name_lower.startswith("fct_") or name_lower.startswith("dim_"):
        return "marts"
    return "other"


def _resolve_model_id(model_name: str, manifest: DbtManifest) -> str:
    """Look up the unique_id for a model by its short name. Raises ValueError if not found."""
    for unique_id, node in manifest.models.items():
        if node.name == model_name:
            return unique_id
    available = ", ".join(n.name for n in manifest.models.values())
    raise ValueError(
        f"Model '{model_name}' not found in manifest. Available models: {available}"
    )


def _node_info(unique_id: str, manifest: DbtManifest) -> dict:
    """Return a summary dict for a node, suitable for JSON serialisation."""
    if unique_id in manifest.models:
        node = manifest.models[unique_id]
        return {
            "unique_id": unique_id,
            "name": node.name,
            "layer": classify_layer(node.fqn, node.name),
            "type": "model",
        }
    if unique_id in manifest.sources:
        source = manifest.sources[unique_id]
        return {
            "unique_id": unique_id,
            "name": source.name,
            "layer": "source",
            "type": "source",
        }
    return {
        "unique_id": unique_id,
        "name": unique_id.split(".")[-1],
        "layer": "unknown",
        "type": "unknown",
    }


def get_lineage(
    model_name: str,
    direction: str,
    depth: int,
    manifest: DbtManifest,
    graph: nx.DiGraph,
) -> dict:
    """Traverse the dependency graph upstream or downstream from a named model."""
    try:
        node_id = _resolve_model_id(model_name, manifest)
    except ValueError as exc:
        return {
            "model_name": model_name,
            "direction": direction,
            "depth": depth,
            "nodes": [],
            "error": str(exc),
        }

    depth_limit = depth if depth > 0 else None

    if direction == "upstream":
        traversal = nx.bfs_tree(graph.reverse(copy=False), node_id, depth_limit=depth_limit)
    else:
        traversal = nx.bfs_tree(graph, node_id, depth_limit=depth_limit)

    related_ids = [n for n in traversal.nodes() if n != node_id]
    nodes = [_node_info(uid, manifest) for uid in related_ids]

    return {
        "model_name": model_name,
        "direction": direction,
        "depth": depth,
        "nodes": nodes,
        "error": None,
    }


def blast_radius(model_name: str, manifest: DbtManifest, graph: nx.DiGraph) -> dict:
    """Return all downstream dependents of a model, grouped by dbt layer."""
    try:
        node_id = _resolve_model_id(model_name, manifest)
    except ValueError as exc:
        return {
            "model_name": model_name,
            "total_affected": 0,
            "by_layer": {},
            "error": str(exc),
        }

    descendants = nx.descendants(graph, node_id)
    model_descendants = [uid for uid in descendants if uid in manifest.models]

    by_layer: dict[str, list[str]] = {}
    for uid in model_descendants:
        node = manifest.models[uid]
        layer = classify_layer(node.fqn, node.name)
        by_layer.setdefault(layer, []).append(node.name)

    return {
        "model_name": model_name,
        "total_affected": len(model_descendants),
        "by_layer": by_layer,
        "error": None,
    }


def search_models(
    query: str,
    collection,
    manifest: DbtManifest | None = None,
    n_results: int = 10,
) -> dict:
    """Search models by query. Uses metadata filters for 'no tests' and 'pii'; otherwise semantic search."""
    query_lower = query.lower()

    if "no test" in query_lower or "without test" in query_lower or "missing test" in query_lower:
        raw = collection.get(where={"has_tests": False}, include=["metadatas", "documents"])
        return {"query": query, "results": _format_get_results(raw)}

    if "pii" in query_lower or "personal" in query_lower:
        raw = collection.get(where={"has_pii": True}, include=["metadatas", "documents"])
        return {"query": query, "results": _format_get_results(raw)}

    # Generic semantic search
    try:
        total = collection.count()
        effective_n = min(n_results, max(total, 1))
        results = collection.query(query_texts=[query], n_results=effective_n)
    except Exception:
        results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    items = []
    if results["ids"] and results["ids"][0]:
        for i, uid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            distance = results["distances"][0][i] if results.get("distances") else 0.0
            items.append(_format_item(uid, meta, results["documents"][0][i] if results.get("documents") else "", distance))

    return {"query": query, "results": items}


def _format_get_results(raw: dict) -> list[dict]:
    """Convert a chromadb.get() response to the standard results list."""
    items = []
    for i, uid in enumerate(raw.get("ids", [])):
        meta = raw["metadatas"][i] if raw.get("metadatas") else {}
        doc = raw["documents"][i] if raw.get("documents") else ""
        items.append(_format_item(uid, meta, doc, 0.0))
    return items


def _format_item(uid: str, meta: dict, document: str, distance: float) -> dict:
    return {
        "name": meta.get("name", uid.split(".")[-1]),
        "unique_id": uid,
        "description": document,
        "layer": meta.get("layer", "unknown"),
        "has_tests": meta.get("has_tests", True),
        "column_names": meta.get("column_names", "").split(",") if meta.get("column_names") else [],
        "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
        "distance": distance,
    }
