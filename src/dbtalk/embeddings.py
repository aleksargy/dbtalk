from __future__ import annotations

import chromadb

from dbtalk.manifest import DbtManifest, DbtNode


def _make_document(node: DbtNode) -> str:
    """Build the embedding document text for a model node."""
    col_parts = []
    for col in node.columns.values():
        if col.description:
            col_parts.append(f"{col.name} ({col.description})")
        else:
            col_parts.append(col.name)
    col_text = ", ".join(col_parts) if col_parts else "none"

    all_col_tags = sorted({tag for col in node.columns.values() for tag in col.tags})
    all_tags = sorted(set(node.tags) | set(all_col_tags))
    tag_text = ", ".join(all_tags) if all_tags else "none"
    col_tag_text = ", ".join(all_col_tags) if all_col_tags else "none"
    fqn_path = "/".join(node.fqn)

    return (
        f"{node.name}: {node.description}. "
        f"Columns: {col_text}. "
        f"Tags: {tag_text}. "
        f"Path: {fqn_path}. "
        f"Column tags: {col_tag_text}."
    )


def _classify_layer(node: DbtNode) -> str:
    fqn_path = "/".join(node.fqn).lower()
    name = node.name.lower()
    if "staging" in fqn_path or name.startswith("stg_"):
        return "staging"
    if "intermediate" in fqn_path or name.startswith("int_"):
        return "intermediate"
    if "marts" in fqn_path or name.startswith("fct_") or name.startswith("dim_"):
        return "marts"
    return "other"


def _has_pii(node: DbtNode) -> bool:
    return any("pii" in col.tags for col in node.columns.values())


def build_collection(manifest: DbtManifest) -> chromadb.Collection:
    """Build an ephemeral ChromaDB collection from all model nodes in the manifest."""
    client = chromadb.Client()
    collection = client.get_or_create_collection("dbt_models")

    # Find all model unique_ids that have at least one test depending on them
    tested_models = {
        dep
        for test_node in manifest.test_nodes.values()
        for dep in test_node.depends_on.nodes
        if dep.startswith("model.")
    }

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for unique_id, node in manifest.models.items():
        ids.append(unique_id)
        documents.append(_make_document(node))
        col_names = ",".join(node.columns.keys())
        metadatas.append(
            {
                "unique_id": unique_id,
                "name": node.name,
                "layer": _classify_layer(node),
                "has_tests": unique_id in tested_models,
                "has_pii": _has_pii(node),
                "tags": ",".join(sorted(node.tags)),
                "column_names": col_names,
            }
        )

    if ids:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)

    return collection
