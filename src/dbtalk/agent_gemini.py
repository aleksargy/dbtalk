from __future__ import annotations

import os
from pathlib import Path

from google import genai
from google.genai import types

from dbtalk import embeddings, tools
from dbtalk.manifest import load_manifest

_MODEL = "gemini-2.0-flash-lite"

_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_lineage",
        description="Traverse the dbt dependency graph upstream or downstream from a named model.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "model_name": types.Schema(
                    type="STRING",
                    description="Short name of the dbt model, e.g. 'fct_revenue'",
                ),
                "direction": types.Schema(
                    type="STRING",
                    enum=["upstream", "downstream"],
                    description="Traverse parents (upstream) or children (downstream)",
                ),
                "depth": types.Schema(
                    type="INTEGER",
                    description="Max graph depth to traverse. 0 means unlimited.",
                ),
            },
            required=["model_name", "direction"],
        ),
    ),
    types.FunctionDeclaration(
        name="search_models",
        description="Semantic search over model and column descriptions in the dbt project.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query": types.Schema(
                    type="STRING",
                    description="Natural language search query, e.g. 'models with PII columns'",
                ),
                "n_results": types.Schema(
                    type="INTEGER",
                    description="Maximum number of results to return.",
                ),
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="blast_radius",
        description="Return all downstream dependents of a dbt model, grouped by dbt layer.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "model_name": types.Schema(
                    type="STRING",
                    description="Short name of the dbt model to analyse, e.g. 'stg_orders'",
                ),
            },
            required=["model_name"],
        ),
    ),
]

_TOOLS = [types.Tool(function_declarations=_TOOL_DECLARATIONS)]


def run(question: str, manifest_path: Path) -> str:
    """Load the manifest, build context, call the Gemini API with tool use, return the answer."""
    manifest = load_manifest(manifest_path)
    graph = tools.build_graph(manifest)
    collection = embeddings.build_collection(manifest)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(tools=_TOOLS)

    first_response = client.models.generate_content(
        model=_MODEL,
        contents=question,
        config=config,
    )

    # If the model answered directly without calling a tool, return that answer
    fn_call = None
    for part in first_response.candidates[0].content.parts:
        if part.function_call:
            fn_call = part.function_call
            break

    if fn_call is None:
        return first_response.text or "I could not generate an answer. Please try rephrasing your question."

    tool_result = _dispatch(fn_call, manifest, graph, collection)

    final_response = client.models.generate_content(
        model=_MODEL,
        contents=[
            types.Content(role="user", parts=[types.Part(text=question)]),
            types.Content(role="model", parts=[types.Part(function_call=fn_call)]),
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fn_call.name,
                            response={"result": tool_result},
                        )
                    )
                ],
            ),
        ],
        config=config,
    )

    return final_response.text or "I could not generate an answer. Please try rephrasing your question."


def _dispatch(fn_call, manifest, graph, collection) -> dict:
    """Call the matching tool function and return the result dict."""
    args = dict(fn_call.args)
    name = fn_call.name

    if name == "get_lineage":
        return tools.get_lineage(
            model_name=args["model_name"],
            direction=args["direction"],
            depth=int(args.get("depth", 0)),
            manifest=manifest,
            graph=graph,
        )
    elif name == "blast_radius":
        return tools.blast_radius(
            model_name=args["model_name"],
            manifest=manifest,
            graph=graph,
        )
    elif name == "search_models":
        return tools.search_models(
            query=args["query"],
            collection=collection,
            manifest=manifest,
            n_results=int(args.get("n_results", 10)),
        )
    else:
        return {"error": f"Unknown tool: {name}"}
