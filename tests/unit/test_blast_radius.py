from pathlib import Path

import pytest

from dbtalk.manifest import load_manifest
from dbtalk.tools import blast_radius, build_graph

FIXTURE = Path(__file__).parent.parent / "fixtures" / "manifest.json"


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(FIXTURE)


@pytest.fixture(scope="module")
def graph(manifest):
    return build_graph(manifest)


def test_stg_orders_blast_radius_groups_intermediate(manifest, graph):
    result = blast_radius("stg_orders", manifest, graph)
    assert result["error"] is None
    assert "int_orders" in result["by_layer"].get("intermediate", [])


def test_stg_orders_blast_radius_groups_marts(manifest, graph):
    result = blast_radius("stg_orders", manifest, graph)
    assert set(result["by_layer"].get("marts", [])) == {"fct_revenue", "fct_customers"}


def test_stg_orders_blast_radius_total_count(manifest, graph):
    result = blast_radius("stg_orders", manifest, graph)
    # int_orders + fct_revenue + fct_customers = 3
    assert result["total_affected"] == 3


def test_fct_revenue_has_empty_blast_radius(manifest, graph):
    result = blast_radius("fct_revenue", manifest, graph)
    assert result["total_affected"] == 0
    assert result["by_layer"] == {}
    assert result["error"] is None


def test_stg_customers_blast_radius_covers_all_downstream_mart_models(manifest, graph):
    result = blast_radius("stg_customers", manifest, graph)
    marts = result["by_layer"].get("marts", [])
    assert "fct_revenue" in marts
    assert "fct_customers" in marts


def test_unknown_model_returns_error(manifest, graph):
    result = blast_radius("unknown_model", manifest, graph)
    assert result["error"] is not None
    assert result["total_affected"] == 0
    assert result["by_layer"] == {}
