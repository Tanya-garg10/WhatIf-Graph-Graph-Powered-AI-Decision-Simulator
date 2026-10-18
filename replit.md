# WhatIf Graph

A graph-powered decision simulator that traces hypothetical software-system changes through downstream dependencies.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the FastAPI service (port 8080)
- `pnpm --filter @workspace/whatif-graph run dev` — run the React/Vite frontend
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `PYTHONPATH=artifacts/api-server python -m unittest discover -s artifacts/api-server/tests -v` — run graph simulation unit tests
- Optional env: `FALKORDB_URI` or `FALKORDB_HOST` plus connection settings; without either, the API reports local demo mode
- Optional secret: `OPENAI_API_KEY` for AI-assisted scenario interpretation

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Frontend: React, Vite, Tailwind CSS
- API: Python 3.11 + FastAPI
- Graph: FalkorDB + official Python client; local in-memory fallback when no database is configured
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Optional AI parsing: official OpenAI Python SDK using `OPENAI_API_KEY`

## Where things live

- `artifacts/whatif-graph/` — dashboard and dependency-graph visualization
- `artifacts/api-server/whatif/` — FastAPI service, graph store, and simulator
- `artifacts/api-server/tests/` — local simulation tests
- `lib/api-spec/openapi.yaml` — API contract
- `README.md` — setup, environment, graph model, and example Cypher

## Architecture decisions

- Simulations only read the baseline graph; graph-derived findings and heuristic mitigations stay distinct.
- FalkorDB is selected when a URI or host is configured. Missing configuration activates clearly labeled demo mode; a failed configured connection returns an error rather than silently falling back.
- The sample graph is seeded only when the connected graph has no `:Component` nodes.

## Product

- Users inspect connections, run suggested what-if scenarios or enter their own, and review affected paths, severity, bottlenecks, and mitigations.

## User preferences

- The user requested a premium responsive dark dashboard with violet/blue accents and a complete, runnable hackathon project.

## Gotchas

- The API service uses Python from the Replit-managed environment; local setup also needs `artifacts/api-server/requirements.txt`.
- Keep API request and response shapes in `lib/api-spec/openapi.yaml`; rerun codegen after changes.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
