from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator


class DbtColumn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    data_type: str = ""
    tags: list[str] = []
    meta: dict = {}

    @field_validator("data_type", mode="before")
    @classmethod
    def coerce_null_data_type(cls, v: object) -> str:
        return v if isinstance(v, str) else ""


class DbtNodeDependsOn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nodes: list[str] = []


class DbtNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unique_id: str
    name: str
    resource_type: str
    package_name: str = ""
    fqn: list[str] = []
    path: str = ""
    description: str = ""
    columns: dict[str, DbtColumn] = {}
    depends_on: DbtNodeDependsOn = DbtNodeDependsOn()
    tags: list[str] = []
    config: dict = {}


class DbtSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unique_id: str
    name: str
    source_name: str = ""
    resource_type: str = "source"
    description: str = ""
    columns: dict[str, DbtColumn] = {}
    tags: list[str] = []


class ManifestMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dbt_schema_version: str = ""
    dbt_version: str = ""
    generated_at: str = ""


class DbtManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    metadata: ManifestMetadata = ManifestMetadata()
    nodes: dict[str, DbtNode] = {}
    sources: dict[str, DbtSource] = {}
    parent_map: dict[str, list[str]] = {}
    child_map: dict[str, list[str]] = {}

    @property
    def models(self) -> dict[str, DbtNode]:
        """Return only model nodes (resource_type == 'model')."""
        return {k: v for k, v in self.nodes.items() if v.resource_type == "model"}

    @property
    def test_nodes(self) -> dict[str, DbtNode]:
        """Return only test nodes (resource_type == 'test')."""
        return {k: v for k, v in self.nodes.items() if v.resource_type == "test"}


def load_manifest(path: Path) -> DbtManifest:
    """Read manifest.json from disk, validate it is a dbt v12 manifest, and return parsed models."""
    if not path.exists():
        raise FileNotFoundError(f"manifest.json not found at {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    required_keys = {"nodes", "sources", "parent_map", "child_map"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(
            f"Not a valid dbt manifest (missing required keys: {', '.join(sorted(missing))})"
        )

    schema_version = data.get("metadata", {}).get("dbt_schema_version", "")
    if schema_version and "v12" not in schema_version:
        raise ValueError(
            f"Unsupported manifest schema version: {schema_version!r}. "
            "dbtalk requires dbt manifest schema v12 (dbt Core >= 1.5)."
        )

    return DbtManifest.model_validate(data)
