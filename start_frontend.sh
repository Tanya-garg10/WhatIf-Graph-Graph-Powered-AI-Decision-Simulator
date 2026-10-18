#!/bin/bash
# Start the frontend with the correct API configuration
cd artifacts/whatif-graph
export VITE_API_URL=http://localhost:8888/api
pnpm run dev
