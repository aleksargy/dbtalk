from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic

from dbtalk import embeddings, tools
from dbtalk.manifest import load_manifest

_MODEL = "claude-haiku-4-5-20251001"

_TOOL_SCHEMAS = [
    {
        "name": "get_lineage",
        "description": "Traverse the dbt dependency graph upstream or downstream from a named model.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": "Short name of the dbt model, e.g. 'fct_revenue'",
                },
                "direction": {
                    "type": "string",
                    "enum": ["upstream", "downstream"],
                    "description": "Traverse parents (upstream) or children (downstream)",
                },
                "depth": {
                    "type": "integer",
                    "description": "Max graph depth to traverse. 0 means unlimited.",
                    "default": 0,
                },
            },
            "required": ["model_name", "direction"],
        },
    },
    {
        "name": "search_models",
        "description": (
            "Search for dbt models by meaning, metadata, or governance criteria. "
            "Use this tool for ANY of these query types: "
            "(1) models with no tests / missing test coverage, "
            "(2) models with PII or sensitive columns, "
            "(3) semantic search over model names, descriptions, and column descriptions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query, e.g. 'models with PII columns'",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "blast_radius",
        "description": "Return all downstream dependents of a dbt model, grouped by dbt layer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": "Short name of the dbt model to analyse, e.g. 'stg_orders'",
                },
            },
            "required": ["model_name"],
        },
    },
]


def run(question: str, manifest_path: Path) -> str:
    """Load the manifest, build context, call the Anthropic API with tool use, return the answer."""
    manifest = load_manifest(manifest_path)
    graph = tools.build_graph(manifest)
    collection = embeddings.build_collection(manifest)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    first_response = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        tools=_TOOL_SCHEMAS,
        messages=[{"role": "user", "content": question}],
    )

    # If the model answered directly without calling a tool, return that answer
    tool_block = next((b for b in first_response.content if b.type == "tool_use"), None)
    if tool_block is None:
        for block in first_response.content:
            if hasattr(block, "text"):
                return block.text
        return "I could not generate an answer. Please try rephrasing your question."

    tool_result = _dispatch(tool_block, manifest, graph, collection)

    final_response = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        tools=_TOOL_SCHEMAS,
        messages=[
            {"role": "user", "content": question},
            {"role": "assistant", "content": first_response.content},
            {"role": "user", "content": [tool_result]},
        ],
    )

    for block in final_response.content:
        if hasattr(block, "text"):
            return block.text

    return "I could not generate an answer. Please try rephrasing your question."


def _dispatch(tool_block, manifest, graph, collection) -> dict:
    """Call the matching tool function and wrap the result as a tool_result message."""
    args = tool_block.input

    if tool_block.name == "get_lineage":
        result = tools.get_lineage(
            model_name=args["model_name"],
            direction=args["direction"],
            depth=args.get("depth", 0),
            manifest=manifest,
            graph=graph,
        )
    elif tool_block.name == "blast_radius":
        result = tools.blast_radius(
            model_name=args["model_name"],
            manifest=manifest,
            graph=graph,
        )
    elif tool_block.name == "search_models":
        result = tools.search_models(
            query=args["query"],
            collection=collection,
            manifest=manifest,
            n_results=args.get("n_results", 10),
        )
    else:
        result = {"error": f"Unknown tool: {tool_block.name}"}

    return {
        "type": "tool_result",
        "tool_use_id": tool_block.id,
        "content": json.dumps(result),
    }
