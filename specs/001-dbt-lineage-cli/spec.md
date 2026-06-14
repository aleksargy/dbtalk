# Feature Specification: dbtalk – Natural Language dbt Lineage Explorer

**Feature Branch**: `001-dbt-lineage-cli`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "Build a Python CLI tool called dbtalk..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask Lineage Questions (Priority: P1)

A data engineer runs `dbtalk ask "what does fct_revenue depend on?"` and receives a
plain-English answer listing the upstream models, sources, and their relationships —
without opening any SQL files or navigating the dbt docs UI.

**Why this priority**: Direct lineage queries are the core value of the tool. All other
capabilities depend on the question-answering loop working correctly.

**Independent Test**: Run `dbtalk ask "what does fct_revenue depend on?"
--manifest tests/fixtures/manifest.json` and verify the answer names the correct
upstream models from the fixture manifest.

**Acceptance Scenarios**:

1. **Given** a manifest where `fct_revenue` depends on `int_orders` and `stg_customers`,
   **When** the user asks "what does fct_revenue depend on?",
   **Then** the answer lists both upstream models by name in plain English.
2. **Given** a valid manifest and question, **When** the user runs the command,
   **Then** a complete answer appears within 30 seconds.
3. **Given** a question about a model that does not exist in the manifest,
   **When** the user asks about it, **Then** the tool responds with a helpful
   "model not found" message rather than an error stack trace.

---

### User Story 2 - Blast Radius Analysis (Priority: P2)

A data engineer asks "what breaks if I change stg_orders?" and receives a list of all
downstream dependents, grouped by dbt layer (staging / intermediate / marts), so they
can assess the impact before making a change.

**Why this priority**: Understanding change impact is the second most common daily need
for data engineers working in large dbt projects.

**Independent Test**: Run `dbtalk ask "what breaks if I change stg_orders?"
--manifest tests/fixtures/manifest.json` and verify the answer lists all downstream
dependents grouped by layer, matching the fixture's known dependency graph.

**Acceptance Scenarios**:

1. **Given** `stg_orders` has 2 downstream dependents across 2 dbt layers,
   **When** the user asks "what breaks if I change stg_orders?",
   **Then** the answer groups dependents by staging / intermediate / marts.
2. **Given** a model with no downstream dependents,
   **When** the user asks for its blast radius,
   **Then** the tool says "no downstream models are affected" rather than returning
   an empty list.

---

### User Story 3 - Semantic Metadata Search (Priority: P3)

A data engineer asks "find all models that reference PII columns" or "find models
with no tests" and receives a filtered list of matching models, enabling governance
and quality checks without writing custom scripts.

**Why this priority**: Metadata search enables governance use cases that are valuable
but secondary to lineage queries.

**Independent Test**: Run `dbtalk ask "find models with no tests"
--manifest tests/fixtures/manifest.json` and verify the answer lists only the models
in the fixture that have no attached test nodes.

**Acceptance Scenarios**:

1. **Given** 2 models with no tests in the fixture,
   **When** the user asks "find models with no tests",
   **Then** both models are named in the answer and no tested models appear.
2. **Given** models with columns tagged "pii",
   **When** the user asks "find all models that reference PII columns",
   **Then** only those models and their PII column names appear in the answer.
3. **Given** a query with no strong semantic match,
   **When** the user searches,
   **Then** the tool returns the closest matches with a note that exact matches
   were not found.

---

### Edge Cases

- What happens when `--manifest` points to a file that does not exist?
- What happens when the file at `--manifest` is valid JSON but not a dbt manifest
  (missing required top-level keys)?
- What happens when `ANTHROPIC_API_KEY` is not set?
- What happens when the Anthropic API call fails (network error, rate limit)?
- What happens when the user asks a question unrelated to dbt
  (e.g., "what is the capital of France?")?
- What happens when a model name in the question is ambiguous (partial match to
  multiple models)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST accept a path to a dbt `manifest.json` file via the
  `--manifest` flag on the `ask` command.
- **FR-002**: The tool MUST accept a natural language question as a positional argument
  to the `ask` command.
- **FR-003**: The tool MUST answer questions about direct and transitive upstream
  dependencies of a named model (lineage queries).
- **FR-004**: The tool MUST answer questions about all downstream dependents of a named
  model, grouped by dbt layer (staging / intermediate / marts).
- **FR-005**: The tool MUST answer questions that require semantic search over model
  and column descriptions (e.g., "models touching customers source",
  "models with PII columns").
- **FR-006**: The tool MUST answer questions about models that lack test coverage.
- **FR-007**: The tool MUST produce plain-English answers that cite model names
  from the manifest.
- **FR-008**: The tool MUST NOT parse raw `.sql` files; all data MUST come from
  `manifest.json` only.
- **FR-009**: The tool MUST exit with a non-zero status code and a clear human-readable
  error message when the manifest file is missing or malformed.
- **FR-010**: The tool MUST exit with a non-zero status code and a clear error message
  when the API key is absent or the API call fails.
- **FR-011**: The tool MUST NOT require any setup steps (database servers, dbt installed,
  Python environment) beyond what is available inside a standard Docker container.

### Key Entities

- **DbtModel**: A dbt model node — name, description, upstream dependencies, columns,
  tags, and whether tests are attached.
- **DbtSource**: A source table declared in dbt — source name, table name, description,
  and columns.
- **DbtColumn**: A column within a model or source — name, description, data type,
  and optional metadata tags (e.g., "pii").
- **LineageGraph**: The directed dependency graph built from the manifest's parent and
  child maps, used for upstream traversal and downstream blast-radius queries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A data engineer can get a correct lineage answer for any model in a
  50-model manifest within 30 seconds of running the command.
- **SC-002**: The blast-radius answer correctly identifies 100% of downstream dependents
  for any model present in the fixture manifest, with zero missing nodes.
- **SC-003**: The semantic search correctly returns all models matching a governance
  query (e.g., "no tests", "PII columns") with zero false negatives on the fixture
  manifest.
- **SC-004**: The tool produces its first visible output within 5 seconds of invocation
  (excluding Anthropic API latency).
- **SC-005**: A data engineer unfamiliar with the tool can run their first successful
  query within 5 minutes of cloning the repository, following only the README.

## Assumptions

- Users have already run `dbt docs generate` or `dbt compile` and have a
  `manifest.json` file available.
- `ANTHROPIC_API_KEY` is available as a shell environment variable or Docker `--env` flag.
- The tool is used interactively by a single user at a time (not as a shared service).
- dbt manifest schema version 12 (dbt Core ≥ 1.5) is the minimum supported format.
- Model layer classification (staging / intermediate / marts) is inferred from the
  model's folder path or name prefix, not from explicit dbt config.
- The fixture manifest used in tests is synthetic and does not require a real dbt
  project or database connection.
- Mobile and browser-based access are out of scope; this is a terminal-only tool.
