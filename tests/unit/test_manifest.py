import json
from pathlib import Path

import pytest

from dbtalk.manifest import DbtManifest, load_manifest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "manifest.json"


def test_load_fixture_returns_manifest():
    manifest = load_manifest(FIXTURE)
    assert isinstance(manifest, DbtManifest)


def test_fixture_has_six_models():
    manifest = load_manifest(FIXTURE)
    assert len(manifest.models) == 6


def test_fixture_has_three_sources():
    manifest = load_manifest(FIXTURE)
    assert len(manifest.sources) == 3


def test_models_property_only_returns_model_nodes():
    manifest = load_manifest(FIXTURE)
    for node in manifest.models.values():
        assert node.resource_type == "model"


def test_test_nodes_property_only_returns_test_nodes():
    manifest = load_manifest(FIXTURE)
    for node in manifest.test_nodes.values():
        assert node.resource_type == "test"


def test_fixture_has_four_test_nodes():
    manifest = load_manifest(FIXTURE)
    assert len(manifest.test_nodes) == 4


def test_stg_customers_has_pii_column():
    manifest = load_manifest(FIXTURE)
    node = manifest.models["model.jaffle_shop.stg_customers"]
    pii_columns = [col for col in node.columns.values() if "pii" in col.tags]
    assert len(pii_columns) >= 1


def test_missing_path_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_manifest(Path("/nonexistent/manifest.json"))


def test_empty_json_raises_value_error(tmp_path):
    bad = tmp_path / "manifest.json"
    bad.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required keys"):
        load_manifest(bad)


def test_wrong_schema_version_raises_value_error(tmp_path):
    data = {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v9/manifest.json"},
        "nodes": {},
        "sources": {},
        "parent_map": {},
        "child_map": {},
    }
    bad = tmp_path / "manifest.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="schema version"):
        load_manifest(bad)
