from pathlib import Path

import pytest

from dbtalk.embeddings import build_collection
from dbtalk.manifest import load_manifest
from dbtalk.tools import search_models

FIXTURE = Path(__file__).parent.parent / "fixtures" / "manifest.json"


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(FIXTURE)


@pytest.fixture(scope="module")
def collection(manifest):
    return build_collection(manifest)


def test_build_collection_stores_has_tests_false_for_stg_orders(manifest, collection):
    results = collection.get(where={"has_tests": False}, include=["metadatas"])
    names = {meta["name"] for meta in results["metadatas"]}
    assert "stg_orders" in names


def test_build_collection_stores_has_tests_false_for_fct_customers(manifest, collection):
    results = collection.get(where={"has_tests": False}, include=["metadatas"])
    names = {meta["name"] for meta in results["metadatas"]}
    assert "fct_customers" in names


def test_build_collection_marks_tested_models_true(manifest, collection):
    results = collection.get(where={"has_tests": True}, include=["metadatas"])
    names = {meta["name"] for meta in results["metadatas"]}
    assert "stg_customers" in names
    assert "int_orders" in names
    assert "fct_revenue" in names


def test_build_collection_marks_stg_customers_has_pii(manifest, collection):
    results = collection.get(where={"has_pii": True}, include=["metadatas"])
    names = {meta["name"] for meta in results["metadatas"]}
    assert "stg_customers" in names


def test_no_tests_query_returns_stg_orders(manifest, collection):
    result = search_models("find models with no tests", collection, manifest)
    names = {r["name"] for r in result["results"]}
    assert "stg_orders" in names


def test_no_tests_query_returns_fct_customers(manifest, collection):
    result = search_models("models with no tests", collection, manifest)
    names = {r["name"] for r in result["results"]}
    assert "fct_customers" in names


def test_no_tests_query_excludes_tested_models(manifest, collection):
    result = search_models("find models with no tests", collection, manifest)
    names = {r["name"] for r in result["results"]}
    assert "stg_customers" not in names
    assert "int_orders" not in names
    assert "fct_revenue" not in names


def test_pii_query_returns_stg_customers(manifest, collection):
    result = search_models("find all models that reference PII columns", collection, manifest)
    names = {r["name"] for r in result["results"]}
    assert "stg_customers" in names


def test_semantic_search_returns_customers_model(manifest, collection):
    result = search_models("customers data", collection, manifest)
    top_names = [r["name"] for r in result["results"][:3]]
    assert "stg_customers" in top_names
