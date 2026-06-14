---
description: "Task list for dbtalk â€“ Natural Language dbt Lineage Explorer"
---

# Tasks: dbtalk â€“ Natural Language dbt Lineage Explorer

**Input**: Design documents from `/specs/001-dbt-lineage-cli/`

**Prerequisites**: plan.md âœ… spec.md âœ… research.md âœ… data-model.md âœ… contracts/cli.md âœ…

**Tests**: Included â€” mandated by Constitution Principle VII (fixture-based testing).
All tests use `tests/fixtures/manifest.json`; zero network calls.

**Organization**: Grouped by user story. Each story is independently completable and testable.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are relative to the repository root

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create all scaffolding so the project is installable and the test runner works.

- [X] T001 Create `pyproject.toml` with `[project]` metadata, approved dependencies (`anthropic`, `click`, `chromadb`, `pydantic`, `rich`, `networkx`), dev extras (`pytest`), and `[project.scripts]` entry point `dbtalk = "dbtalk.cli:cli"`
- [X] T002 [P] Create `src/dbtalk/__init__.py` and five empty module files: `src/dbtalk/manifest.py`, `src/dbtalk/embeddings.py`, `src/dbtalk/tools.py`, `src/dbtalk/agent.py`, `src/dbtalk/cli.py`
- [X] T003 [P] Create `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, and empty `tests/fixtures/` directory
- [X] T004 [P] Create `Dockerfile` using `python:3.12-slim` single-stage build: copy `src/` + `pyproject.toml`, run `pip install .`, set `ENTRYPOINT ["dbtalk"]`
- [X] T005 [P] Create `.env.example` with `ANTHROPIC_API_KEY=sk-ant-...` and a comment explaining it must be set in the shell or via `docker --env`

**Checkpoint**: `pip install -e ".[dev]"` installs without error; `dbtalk --help` exits 0.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Manifest parsing and the fixture manifest must be complete before any user story
can be implemented or tested. No user story work can begin until this phase is done.

**âš ï¸ CRITICAL**: Phases 3â€“5 all depend on T006 and T007.

- [X] T006 Create `tests/fixtures/manifest.json` â€” synthetic dbt manifest (schema v12) with exactly 6 model nodes, 3 source nodes, and 3 test nodes. Models: `stg_customers` (staging, has tests, PII column `email` tagged `["pii"]`), `stg_orders` (staging, **no tests**), `stg_payments` (staging, has tests), `int_orders` (intermediate, has tests, depends on stg_orders + stg_payments), `fct_revenue` (marts, has tests, depends on int_orders + stg_customers), `fct_customers` (marts, **no tests**, depends on stg_customers + int_orders). Include `parent_map` and `child_map` entries for all 9 nodes (6 models + 3 sources).
- [X] T007 Implement `src/dbtalk/manifest.py`: define `DbtColumn`, `DbtNodeDependsOn`, `DbtNode`, `DbtSource`, `ManifestMetadata`, `DbtManifest` Pydantic models with `model_config = {"extra": "ignore"}`; add `.models` and `.test_nodes` properties to `DbtManifest`; add `load_manifest(path: Path) -> DbtManifest` function that reads JSON, validates schema version contains "v12", raises `ValueError` with a clear message if invalid
- [X] T008 [P] Write `tests/unit/test_manifest.py`: test that loading `tests/fixtures/manifest.json` returns a `DbtManifest` with 6 models and 3 sources; test `.models` returns only `resource_type == "model"` nodes; test `.test_nodes` returns only test nodes; test that loading a non-existent path raises `FileNotFoundError`; test that a JSON file missing `nodes` key raises `ValueError`

**Checkpoint**: `pytest tests/unit/test_manifest.py` passes with zero network calls.

---

## Phase 3: User Story 1 â€“ Ask Lineage Questions (Priority: P1) ðŸŽ¯ MVP

**Goal**: A data engineer can run `dbtalk ask "what does fct_revenue depend on?"` and receive
a plain-English answer listing upstream models and sources.

**Independent Test**: `dbtalk ask "what does fct_revenue depend on?" --manifest tests/fixtures/manifest.json`
returns an answer naming `int_orders`, `stg_customers`, `stg_orders`, `stg_payments`, and the raw sources.

### Implementation for User Story 1

- [X] T009 [US1] Implement `build_graph(manifest: DbtManifest) -> nx.DiGraph` in `src/dbtalk/tools.py`: build a directed graph where each node is a `unique_id` and edges go from parent â†’ child using `manifest.parent_map`; store node metadata (name, resource_type) as node attributes
- [X] T010 [US1] Implement `get_lineage(model_name: str, direction: str, depth: int, manifest: DbtManifest, graph: nx.DiGraph) -> dict` in `src/dbtalk/tools.py`: resolve `model_name` to a `unique_id` by searching `manifest.models` (raise clear error if not found); use `nx.bfs_tree(graph.reverse(), node, depth_limit=depth or None)` for upstream and `nx.bfs_tree(graph, node, depth_limit=depth or None)` for downstream; return dict matching the contract in `specs/001-dbt-lineage-cli/contracts/cli.md`
- [X] T011 [P] [US1] Implement `classify_layer(node: DbtNode) -> str` and `blast_radius(model_name: str, manifest: DbtManifest, graph: nx.DiGraph) -> dict` in `src/dbtalk/tools.py`: `classify_layer` returns "staging" / "intermediate" / "marts" / "other" from `node.fqn` path components or name prefix (`stg_` / `int_` / `fct_` or `dim_`); `blast_radius` uses `nx.descendants(graph, node_id)`, classifies each, groups by layer, returns dict matching contract
- [X] T012 [P] [US1] Implement `build_collection(manifest: DbtManifest) -> chromadb.Collection` in `src/dbtalk/embeddings.py`: create ephemeral `chromadb.Client()` and a collection named `"dbt_models"`; for each model, construct document text `"{name}: {description}. Columns: {col} ({col_desc}). Tags: {tags}."` and metadata dict `{unique_id, name, layer, has_tests, tags, column_names}`; call `collection.add(...)` with all documents; return the collection
- [X] T013 [US1] Implement `search_models(query: str, collection: chromadb.Collection, n_results: int = 10) -> dict` in `src/dbtalk/tools.py`: call `collection.query(query_texts=[query], n_results=n_results)`; return dict with `query` and `results` list matching contract; for "no tests" queries also call `collection.get(where={"has_tests": False})` and merge results
- [X] T014 [US1] Implement `run(question: str, manifest_path: Path) -> str` in `src/dbtalk/agent.py`: load manifest via `manifest.load_manifest()`; build graph via `tools.build_graph()`; build ChromaDB collection via `embeddings.build_collection()`; define three Anthropic tool schemas (`get_lineage`, `search_models`, `blast_radius`) matching `specs/001-dbt-lineage-cli/contracts/cli.md`; call `anthropic.Anthropic().messages.create(model="claude-haiku-4-5-20251001", tools=..., messages=[{question}])`; dispatch the returned `tool_use` block to the matching function in `tools.py`; make a second API call with the tool result; return the final text response
- [X] T015 [US1] Implement `src/dbtalk/cli.py`: create a `click.group()` named `cli`; add `@cli.command("ask")` with `argument("question")` and `option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)`; read `ANTHROPIC_API_KEY` from `os.environ` and exit with code 1 and a clear message if missing; show a `rich` spinner on stderr while calling `agent.run()`; print the answer via `rich.print()`; handle `ValueError` (manifest error, exit 2) and `anthropic.APIError` (exit 3) with human-readable messages

### Tests for User Story 1

- [X] T016 [P] [US1] Write `tests/unit/test_tools.py`: test `get_lineage("fct_revenue", "upstream", 0, ...)` returns nodes including `int_orders` and `stg_customers`; test `get_lineage("stg_orders", "downstream", 0, ...)` returns `int_orders`; test `get_lineage` raises a clear error for unknown model name; test `blast_radius("stg_orders", ...)` returns `{"intermediate": ["int_orders"], "marts": ["fct_revenue", "fct_customers"]}` (order-insensitive); test `classify_layer` returns correct layer for each of the 6 fixture models
- [X] T017 [P] [US1] Write `tests/integration/test_cli.py`: use `click.testing.CliRunner` and `unittest.mock.patch("dbtalk.agent.anthropic.Anthropic")` to mock the Anthropic client; test `dbtalk ask "..." --manifest tests/fixtures/manifest.json` exits 0 when the mock returns a valid response; test that missing `ANTHROPIC_API_KEY` exits 1 with the correct error message; test that a non-existent manifest path exits 1

**Checkpoint**: `pytest tests/` passes. `dbtalk ask "what does fct_revenue depend on?" --manifest tests/fixtures/manifest.json` returns a correct answer (with real `ANTHROPIC_API_KEY` set).

---

## Phase 4: User Story 2 â€“ Blast Radius Analysis (Priority: P2)

**Goal**: `dbtalk ask "what breaks if I change stg_orders?"` returns downstream dependents
grouped by dbt layer (staging / intermediate / marts).

**Independent Test**: The answer for `stg_orders` lists `int_orders` under "intermediate" and
`fct_revenue`, `fct_customers` under "marts".

*Note*: `blast_radius()` and `classify_layer()` were implemented in T011 as part of building
the full agent pipeline. This phase adds targeted tests and validates the layer grouping logic
with all fixture models.

### Tests for User Story 2

- [X] T018 [P] [US2] Write `tests/unit/test_blast_radius.py`: test `blast_radius("stg_orders", ...)` groups exactly `int_orders` in intermediate and `fct_revenue` + `fct_customers` in marts; test `blast_radius("fct_revenue", ...)` returns empty `by_layer` and `total_affected = 0`; test `blast_radius("stg_customers", ...)` includes both `fct_revenue` and `fct_customers` in marts; test unknown model name returns `error` field with a descriptive message
- [X] T019 [P] [US2] Write integration test in `tests/integration/test_cli.py` (extend existing file): add a test verifying that when the mock Anthropic client dispatches `blast_radius`, the CLI receives and prints the grouped result without error

**Checkpoint**: `pytest tests/unit/test_blast_radius.py` passes. `dbtalk ask "what breaks if I change stg_orders?" --manifest tests/fixtures/manifest.json` shows grouped output.

---

## Phase 5: User Story 3 â€“ Semantic Metadata Search (Priority: P3)

**Goal**: `dbtalk ask "find models with no tests"` returns `stg_orders` and `fct_customers`.
`dbtalk ask "find all models that reference PII columns"` returns `stg_customers`.

**Independent Test**: `search_models("models with no tests", collection)` returns only models
where `has_tests == False` from the fixture.

*Note*: `search_models()` was implemented in T013. This phase enhances the embedding document
to include richer column metadata and adds metadata-filter support for boolean properties.

### Implementation for User Story 3

- [X] T020 [US3] Enhance `build_collection()` in `src/dbtalk/embeddings.py`: extend each document to append column-level detail `"Column tags: {all_column_tags}."` so PII tags are searchable via embedding; store `"has_pii": True/False` in per-document metadata (True if any column has "pii" in its tags); re-verify that `has_tests` metadata is stored as a Python `bool` (ChromaDB `where` filters require native bool)
- [X] T021 [US3] Enhance `search_models()` in `src/dbtalk/tools.py`: add `where` filter support â€” if the query contains "no tests" or "without tests", add `where={"has_tests": False}` to the ChromaDB query; if the query contains "pii", add `where={"has_pii": True}`; merge filtered results with semantic search results and deduplicate

### Tests for User Story 3

- [X] T022 [P] [US3] Write `tests/unit/test_search.py`: test that `search_models("find models with no tests", collection)` returns exactly `stg_orders` and `fct_customers`; test that `search_models("models that reference PII columns", collection)` returns `stg_customers`; test that `search_models("customers data", collection)` returns at least `stg_customers` in the top 3 results; test that `build_collection()` stores `has_tests=False` for `stg_orders` and `fct_customers`

**Checkpoint**: `pytest tests/unit/test_search.py` passes. Governance queries return correct models from fixture.

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that apply across all user stories.

- [X] T023 [P] Write `README.md`: Docker-first usage section with copy-pasteable `docker build` and `docker run` commands; local venv setup section; five example `dbtalk ask` commands from the spec; "Common Errors" table (missing API key, wrong manifest path, non-dbt JSON); link to `specs/001-dbt-lineage-cli/quickstart.md`
- [X] T024 [P] Add `rich.console.Console().status(...)` spinner in `src/dbtalk/cli.py` wrapping the `agent.run()` call; suppress spinner when stdout is not a TTY (`if not sys.stdout.isatty()`)
- [X] T025 Validate `docker build -t dbtalk .` completes without error and `docker run --rm -e ANTHROPIC_API_KEY=dummy dbtalk --help` exits 0
- [X] T026 [P] Add error-path tests in `tests/unit/test_manifest.py`: loading a path that exists but contains `{}` (not a dbt manifest) raises `ValueError` with "missing required keys"; loading a manifest with schema version "v9" raises `ValueError` with "schema version"
- [X] T027 [P] Run `pytest tests/ -v` and confirm all tests pass; run `pip install -e ".[dev]" && dbtalk --help` to confirm entry point is wired correctly

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion â€” **blocks all user stories**
- **User Story 1 (Phase 3)**: Depends on Phase 2 â€” implements the full 5-module pipeline
- **User Story 2 (Phase 4)**: Depends on Phase 3 (blast_radius implemented in T011) â€” adds targeted tests
- **User Story 3 (Phase 5)**: Depends on Phase 3 (search_models implemented in T013) â€” enhances embeddings
- **Polish (Phase N)**: Depends on Phases 3â€“5 being complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational â€” no dependency on US2 or US3
- **US2 (P2)**: Depends on US1 (blast_radius and classify_layer are implemented in Phase 3)
- **US3 (P3)**: Depends on US1 (search_models and build_collection are implemented in Phase 3)

### Within Each Phase

- Models before services (T007 before T009â€“T013)
- Tools before agent (T009â€“T013 before T014)
- Agent before CLI (T014 before T015)
- Tests come after implementation (test files can be written after the module they test exists)

### Parallel Opportunities

Tasks marked [P] have no dependency on other incomplete tasks in their phase:
- Phase 1: T002, T003, T004, T005 can all run in parallel after T001
- Phase 2: T008 can start after T007 (needs the module to test)
- Phase 3: T011 (blast_radius) and T012 (embeddings) can run in parallel with T010; T016 and T017 can run after T015

---

## Parallel Example: Phase 3

```text
# After T009 (build_graph) completes:
Parallel group A: T010 (get_lineage) || T011 (blast_radius) || T012 (build_collection)

# After T010 and T012 complete:
T013 (search_models)  [depends on T012]

# After T010, T011, T013 complete:
T014 (agent.py)

# After T014:
T015 (cli.py)

# After T015 (all modules exist):
Parallel group B: T016 (test_tools.py) || T017 (test_cli.py)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational â€” fixture manifest + manifest.py
3. Complete Phase 3: US1 â€” all 5 modules + tests
4. **STOP and VALIDATE**: `dbtalk ask "what does fct_revenue depend on?" --manifest tests/fixtures/manifest.json`
5. Deploy Docker image if answer is correct

### Incremental Delivery

1. Phase 1 + 2 â†’ Project installs and test infrastructure works
2. Phase 3 â†’ Full pipeline; lineage questions work â†’ **MVP**
3. Phase 4 â†’ Blast radius grouping verified
4. Phase 5 â†’ Governance queries work
5. Phase N â†’ Docker validated; README published

---

## Notes

- [P] tasks = operate on different files with no dependency on incomplete tasks in the same phase
- [US1/US2/US3] label maps each task to its user story for traceability
- All test files MUST import only from `dbtalk.*` and `tests.fixtures`; no network calls
- The Anthropic client MUST be mocked in all `tests/` files â€” never make real API calls in tests
- `classify_layer()` is a pure function with no I/O â€” test it with direct unit tests, not integration tests
- Constitution Principle VIII: keep all functions â‰¤ 30 lines; use plain names (`manifest_path`, not `mp`)

