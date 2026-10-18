# WhatIf Graph

WhatIf Graph is a graph-powered decision simulator for engineering teams. It lets users select a software-system component, describe a hypothetical change, and trace downstream effects without changing the baseline graph.

## What it does

- Displays a seven-component e-commerce dependency graph.
- Supports scenarios for service outages, database delays, and engineering-team capacity loss.
- Uses multi-hop graph traversal to calculate affected components and dependency paths.
- Shows risk, likely bottlenecks, and heuristic mitigation suggestions in a comparison report.
- Clearly labels whether the graph is stored in FalkorDB or served from local demo mode.
- Keeps hypothetical simulations read-only; only initial graph seeding writes to FalkorDB, and only when the `:Component` graph is empty.

## Architecture

- **Frontend:** React, TypeScript, Vite, Tailwind CSS.
- **API:** Python 3.11, FastAPI.
- **Graph database:** FalkorDB with the official `falkordb` Python client and Cypher queries.
- **API contract:** `lib/api-spec/openapi.yaml`; generated React Query hooks and validation schemas live in the shared `lib/api-client-react` and `lib/api-zod` packages.
- **Optional AI parsing:** The official OpenAI Python SDK can map free-text scenarios to a component and event type. Graph traversal computes all impact facts; mitigation advice remains heuristic and is labeled accordingly. Without a valid `OPENAI_API_KEY`, rule-based scenario parsing is used.

The API is exposed under `/api`:

- `GET /api/healthz` — service health (`ok` or `degraded`).
- `GET /api/graph` — baseline nodes, edges, graph backend, and configuration status.
- `POST /api/simulate` — impact report for a hypothetical scenario.

## Run in the Replit workspace

Install JavaScript and Python dependencies if they are not already installed:

```bash
pnpm install
python -m pip install -r artifacts/api-server/requirements.txt
```

Run the two configured services in separate terminals, or start the matching API Server and WhatIf Graph workflows:

```bash
pnpm --filter @workspace/api-server run dev
pnpm --filter @workspace/whatif-graph run dev
```

The managed workflows supply the service ports, preview base path, and `/api` routing. For a standalone deployment outside this workspace, serve the web app and API behind a same-origin reverse proxy that routes `/api/*` to the FastAPI service.

## Environment variables

### FalkorDB

Configure either a URI or individual connection settings:

| Variable | Purpose |
| --- | --- |
| `FALKORDB_URI` or `FALKORDB_URL` | Redis-compatible `redis://` or `rediss://` FalkorDB connection URI |
| `FALKORDB_HOST` | Hostname; use this instead of a URI when configuring fields separately |
| `FALKORDB_PORT` | Port; defaults to `6379` |
| `FALKORDB_USERNAME` | Optional database username |
| `FALKORDB_PASSWORD` | Optional database password |
| `FALKORDB_SSL` | Enable TLS for field-based configuration (`true`/`false`) |
| `FALKORDB_GRAPH_NAME` | Graph name; defaults to `whatif_graph` |
| `FALKORDB_CONNECT_TIMEOUT` | Connection timeout in seconds; defaults to `4` |

If neither a URI nor a host is set, the application uses an in-memory demo graph and reports `backend: demo`. If FalkorDB is configured but unavailable, the API returns an explicit error instead of quietly pretending to use FalkorDB or silently switching to demo mode.

### Optional AI interpretation

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Secret used for model-assisted scenario parsing |
| `OPENAI_BASE_URL` | Optional OpenAI-compatible API base URL |
| `OPENAI_MODEL` | Model name; defaults to `gpt-5-nano` |

Add `OPENAI_API_KEY` through Replit Secrets or your deployment's secret manager. Do not commit secrets to the repository. The API response reports `analysisMode` as `ai_assisted` or `rule_based`.

## FalkorDB graph model

All sample entities use the `Component` label and have `id`, `name`, `type`, `description`, and `status` properties:

- Payment Service
- Order Service
- Inventory Service
- Notification Service
- Database
- Engineering Team
- Deployment Deadline

Relationship direction:

- `(consumer)-[:DEPENDS_ON]->(dependency)` — the source requires the target.
- `(component)-[:OWNED_BY]->(team)` — the source is owned by the target.
- `(deadline)-[:BLOCKS]->(component)` — the source milestone blocks the target.

When an external graph contains no `:Component` nodes, the app inserts the sample nodes and edges with `MERGE`. A graph that already contains `:Component` nodes is left intact.

### Example Cypher

List a component's dependencies:

```cypher
MATCH (component:Component {id: $componentId})-[:DEPENDS_ON]->(dependency:Component)
RETURN component.name, dependency.name
```

Find all downstream components affected by an unavailable dependency:

```cypher
MATCH path=(affected:Component)-[:DEPENDS_ON*1..5]->(trigger:Component {id: $triggerId})
RETURN [component IN nodes(path) | component.id] AS reversePath
ORDER BY length(path)
```

Find components owned by an engineering team:

```cypher
MATCH (owned:Component)-[:OWNED_BY]->(team:Component {id: $teamId})
RETURN owned.id
```

The simulator reverses the returned dependency paths for display so each report reads from the scenario trigger toward the affected component. Team-loss simulations combine the ownership query with downstream dependency traversal.

## Main scenario flow

1. The user enters or selects a scenario.
2. The API maps the text to one of the graph's existing component IDs and an event type (`outage`, `delay`, or `capacity_loss`).
3. FalkorDB runs parameterized Cypher multi-hop traversal. Demo mode follows the same relationship directions locally.
4. The API returns affected nodes and paths derived from graph relationships, plus separately labeled heuristic mitigations.
5. The simulation performs no writes. Baseline counts and graph status remain visible in the report.

The reported risk is a relative heuristic, not an outage probability or an SLA prediction.

## Project checks

```bash
pnpm run typecheck
PYTHONPATH=artifacts/api-server python -m unittest discover -s artifacts/api-server/tests -v
```

## Limitations

- The supplied graph is a small demonstration model, not a production topology importer.
- Local demo mode is in memory and resets when the API process restarts.
- External database credentials and reachability are environment-specific; the app reports demo mode until FalkorDB is configured.
- AI interpretation is optional. If no API key is configured or the model request fails, the rule-based parser is used and identified in the simulation response.
