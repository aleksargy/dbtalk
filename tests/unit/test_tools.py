from pathlib import Path

import pytest

from dbtalk.manifest import load_manifest
from dbtalk.tools import blast_radius, build_graph, classify_layer, get_lineage

FIXTURE = Path(__file__).parent.parent / "fixtures" / "manifest.json"


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(FIXTURE)


@pytest.fixture(scope="module")
def graph(manifest):
    return build_graph(manifest)


# --- get_lineage ---

def test_get_lineage_upstream_fct_revenue_includes_int_orders(manifest, graph):
    result = get_lineage("fct_revenue", "upstream", 0, manifest, graph)
    names = {n["name"] for n in result["nodes"]}
    assert "int_orders" in names
    assert result["error"] is None


def test_get_lineage_upstream_fct_revenue_includes_stg_customers(manifest, graph):
    result = get_lineage("fct_revenue", "upstream", 0, manifest, graph)
    names = {n["name"] for n in result["nodes"]}
    assert "stg_customers" in names


def test_get_lineage_upstream_fct_revenue_includes_sources(manifest, graph):
    result = get_lineage("fct_revenue", "upstream", 0, manifest, graph)
    types = {n["type"] for n in result["nodes"]}
    assert "source" in types


def test_get_lineage_downstream_stg_orders_includes_int_orders(manifest, graph):
    result = get_lineage("stg_orders", "downstream", 0, manifest, graph)
    names = {n["name"] for n in result["nodes"]}
    assert "int_orders" in names


def test_get_lineage_depth_limits_result(manifest, graph):
    # Depth 1 from stg_orders downstream should only reach int_orders, not fct_revenue
    result = get_lineage("stg_orders", "downstream", 1, manifest, graph)
    names = {n["name"] for n in result["nodes"]}
    assert "int_orders" in names
    assert "fct_revenue" not in names


def test_get_lineage_unknown_model_returns_error(manifest, graph):
    result = get_lineage("nonexistent_model", "upstream", 0, manifest, graph)
    assert result["error"] is not None
    assert len(result["nodes"]) == 0


# --- blast_radius ---

def test_blast_radius_stg_orders_has_intermediate_group(manifest, graph):
    result = blast_radius("stg_orders", manifest, graph)
    assert result["error"] is None
    assert "int_orders" in result["by_layer"].get("intermediate", [])


def test_blast_radius_stg_orders_has_mart_models(manifest, graph):
    result = blast_radius("stg_orders", manifest, graph)
    marts = result["by_layer"].get("marts", [])
    assert "fct_revenue" in marts
    assert "fct_customers" in marts


def test_blast_radius_fct_revenue_has_no_descendants(manifest, graph):
    result = blast_radius("fct_revenue", manifest, graph)
    assert result["total_affected"] == 0
    assert result["by_layer"] == {}


def test_blast_radius_stg_customers_reaches_both_mart_models(manifest, graph):
    result = blast_radius("stg_customers", manifest, graph)
    all_names = [name for names in result["by_layer"].values() for name in names]
    assert "fct_revenue" in all_names
    assert "fct_customers" in all_names


def test_blast_radius_unknown_model_returns_error(manifest, graph):
    result = blast_radius("unknown_model", manifest, graph)
    assert result["error"] is not None
    assert result["total_affected"] == 0


# --- classify_layer ---

def test_classify_layer_staging_by_fqn():
    assert classify_layer(["jaffle_shop", "staging", "stg_orders"], "stg_orders") == "staging"


def test_classify_layer_staging_by_name_prefix():
    assert classify_layer(["jaffle_shop", "models", "stg_orders"], "stg_orders") == "staging"


def test_classify_layer_intermediate_by_fqn():
    assert classify_layer(["jaffle_shop", "intermediate", "int_orders"], "int_orders") == "intermediate"


def test_classify_layer_intermediate_by_name_prefix():
    assert classify_layer(["jaffle_shop", "models", "int_orders"], "int_orders") == "intermediate"


def test_classify_layer_marts_by_fqn():
    assert classify_layer(["jaffle_shop", "marts", "fct_revenue"], "fct_revenue") == "marts"


def test_classify_layer_marts_by_fct_prefix():
    assert classify_layer(["jaffle_shop", "models", "fct_revenue"], "fct_revenue") == "marts"


def test_classify_layer_other_for_unknown_pattern():
    assert classify_layer(["jaffle_shop", "custom", "weird_model"], "weird_model") == "other"
