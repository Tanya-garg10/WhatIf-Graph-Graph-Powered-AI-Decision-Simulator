from __future__ import annotations

import os
from collections import deque
from typing import Any
from falkordb import FalkorDB

GRAPH_NAME = os.getenv("FALKORDB_GRAPH_NAME", "whatif_graph")
MAX_PATH_DEPTH = 6

BASE_NODES: list[dict[str, str]] = [
    {
        "id": "payment-service",
        "name": "Payment Service",
        "type": "service",
        "description": "Authorizes and captures customer payments.",
        "status": "Operational",
    },
    {
        "id": "order-service",
        "name": "Order Service",
        "type": "service",
        "description": "Coordinates checkout and order fulfillment.",
        "status": "Operational",
    },
    {
        "id": "inventory-service",
        "name": "Inventory Service",
        "type": "service",
        "description": "Tracks stock and reserves items for orders.",
        "status": "Operational",
    },
    {
        "id": "notification-service",
        "name": "Notification Service",
        "type": "service",
        "description": "Sends order confirmations and status updates.",
        "status": "Operational",
    },
    {
        "id": "database",
        "name": "Database",
        "type": "database",
        "description": "Primary persistence layer for commerce data.",
        "status": "Operational",
    },
    {
        "id": "engineering-team",
        "name": "Engineering Team",
        "type": "team",
        "description": "Owns and supports the commerce services.",
        "status": "Available",
    },
    {
        "id": "deployment-deadline",
        "name": "Deployment Deadline",
        "type": "milestone",
        "description": "Release readiness milestone for the commerce stack.",
        "status": "On track",
    },
]

# DEPENDS_ON points from a consumer to its dependency. OWNED_BY points from a
# component to its owner. BLOCKS points from the blocking milestone to its target.
BASE_EDGES: list[dict[str, str]] = [
    {"source": "order-service", "target": "payment-service", "relationship": "DEPENDS_ON"},
    {"source": "order-service", "target": "inventory-service", "relationship": "DEPENDS_ON"},
    {"source": "order-service", "target": "database", "relationship": "DEPENDS_ON"},
    {"source": "payment-service", "target": "database", "relationship": "DEPENDS_ON"},
    {"source": "inventory-service", "target": "database", "relationship": "DEPENDS_ON"},
    {"source": "notification-service", "target": "order-service", "relationship": "DEPENDS_ON"},
    {"source": "payment-service", "target": "engineering-team", "relationship": "OWNED_BY"},
    {"source": "order-service", "target": "engineering-team", "relationship": "OWNED_BY"},
    {"source": "inventory-service", "target": "engineering-team", "relationship": "OWNED_BY"},
    {"source": "notification-service", "target": "engineering-team", "relationship": "OWNED_BY"},
    {"source": "database", "target": "engineering-team", "relationship": "OWNED_BY"},
    {"source": "deployment-deadline", "target": "order-service", "relationship": "BLOCKS"},
]


class GraphUnavailable(RuntimeError):
    """Raised when FalkorDB is configured but cannot be reached."""


class GraphStore:
    backend = "demo"
    database_connected = False
    graph_name = "local-demo"
    error: str | None = None

    def get_graph(self) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        return [dict(node) for node in BASE_NODES], [dict(edge) for edge in BASE_EDGES]

    def dependent_paths(self, trigger_id: str) -> list[list[str]]:
        nodes, edges = self.get_graph()
        node_ids = {node["id"] for node in nodes}
        if trigger_id not in node_ids:
            return []

        dependents: dict[str, list[str]] = {}
        for edge in edges:
            if edge["relationship"] == "DEPENDS_ON":
                dependents.setdefault(edge["target"], []).append(edge["source"])

        trigger_type = next(node for node in nodes if node["id"] == trigger_id)["type"]
        if trigger_type == "team":
            starts = [
                (edge["source"], [trigger_id, edge["source"]])
                for edge in edges
                if edge["relationship"] == "OWNED_BY" and edge["target"] == trigger_id
            ]
        elif trigger_type == "milestone":
            starts = [
                (edge["target"], [trigger_id, edge["target"]])
                for edge in edges
                if edge["relationship"] == "BLOCKS" and edge["source"] == trigger_id
            ]
        else:
            starts = [(trigger_id, [trigger_id])]

        found: dict[str, list[str]] = {}
        queue: deque[tuple[str, list[str]]] = deque(starts)
        while queue:
            current, path = queue.popleft()
            if len(path) > 1:
                found.setdefault(current, path)
            if len(path) - 1 >= MAX_PATH_DEPTH:
                continue
            for dependent in dependents.get(current, []):
                if dependent not in path:
                    queue.append((dependent, [*path, dependent]))

        return sorted(found.values(), key=lambda path: (len(path), path[-1]))

    def close(self) -> None:
        return None


class FalkorGraphStore(GraphStore):
    backend = "falkordb"
    database_connected = True

    def __init__(self, client: FalkorDB, graph: Any, graph_name: str):
        self.client = client
        self.graph = graph
        self.graph_name = graph_name
        self._seed_if_empty()

    @classmethod
    def from_environment(cls) -> GraphStore:
        uri = os.getenv("FALKORDB_URI") or os.getenv("FALKORDB_URL")
        host = os.getenv("FALKORDB_HOST")
        if not uri and not host:
            return GraphStore()

        try:
            timeout = min(max(float(os.getenv("FALKORDB_CONNECT_TIMEOUT", "4")), 0.5), 30.0)
        except ValueError:
            return UnavailableGraphStore(
                "FALKORDB_CONNECT_TIMEOUT must be a number between 0.5 and 30 seconds."
            )
        client = None
        try:
            if uri:
                client = FalkorDB.from_url(
                    uri,
                    socket_connect_timeout=timeout,
                    socket_timeout=timeout,
                )
            else:
                client = FalkorDB(
                    host=host,
                    port=int(os.getenv("FALKORDB_PORT", "6379")),
                    username=os.getenv("FALKORDB_USERNAME") or None,
                    password=os.getenv("FALKORDB_PASSWORD") or None,
                    ssl=os.getenv("FALKORDB_SSL", "false").lower() in {"1", "true", "yes"},
                    socket_connect_timeout=timeout,
                    socket_timeout=timeout,
                )
            graph_name = os.getenv("FALKORDB_GRAPH_NAME", "whatif_graph")
            graph = client.select_graph(graph_name)
            graph.query("RETURN 1 AS ready", timeout=timeout * 1000)
            return cls(client, graph, graph_name)
        except Exception:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            # Do not silently fall back when the user explicitly configured a DB.
            return UnavailableGraphStore(
                "FalkorDB is configured but could not be reached. Check its address, port, TLS, and credentials."
            )

    def _query(self, query: str, params: dict[str, Any] | None = None) -> list[list[Any]]:
        result = self.graph.query(query, params=params, timeout=5000)
        return result.result_set or []

    def _seed_if_empty(self) -> None:
        rows = self._query("MATCH (n:Component) RETURN count(n) AS count")
        count = int(rows[0][0]) if rows else 0
        if count:
            return

        self._query(
            """
            UNWIND $nodes AS item
            MERGE (node:Component {id: item.id})
            SET node.name = item.name,
                node.type = item.type,
                node.description = item.description,
                node.status = item.status
            """,
            {"nodes": BASE_NODES},
        )
        for relationship in ("DEPENDS_ON", "OWNED_BY", "BLOCKS"):
            matching_edges = [
                {"source": edge["source"], "target": edge["target"]}
                for edge in BASE_EDGES
                if edge["relationship"] == relationship
            ]
            if not matching_edges:
                continue
            self._query(
                f"""
                UNWIND $edges AS item
                MATCH (source:Component {{id: item.source}})
                MATCH (target:Component {{id: item.target}})
                MERGE (source)-[:{relationship}]->(target)
                """,
                {"edges": matching_edges},
            )

    def get_graph(self) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        node_rows = self._query(
            """
            MATCH (node:Component)
            RETURN node.id, node.name, node.type, node.description, node.status
            ORDER BY node.name
            """
        )
        edge_rows = self._query(
            """
            MATCH (source:Component)-[relationship]->(target:Component)
            RETURN source.id, target.id, type(relationship)
            ORDER BY source.name, target.name
            """
        )
        nodes = [
            {
                "id": str(row[0]),
                "name": str(row[1]),
                "type": str(row[2]),
                "description": str(row[3]),
                "status": str(row[4]),
            }
            for row in node_rows
        ]
        edges = [
            {
                "source": str(row[0]),
                "target": str(row[1]),
                "relationship": str(row[2]),
            }
            for row in edge_rows
        ]
        return nodes, edges

    def dependent_paths(self, trigger_id: str) -> list[list[str]]:
        nodes, _ = self.get_graph()
        trigger = next((node for node in nodes if node["id"] == trigger_id), None)
        if trigger is None:
            return []

        paths: dict[str, list[str]] = {}
        if trigger["type"] == "team":
            owner_rows = self._query(
                """
                MATCH (owned:Component)-[:OWNED_BY]->(team:Component {id: $triggerId})
                RETURN owned.id
                """,
                {"triggerId": trigger_id},
            )
            for owner_row in owner_rows:
                owned_id = str(owner_row[0])
                dependent_rows = self._query(
                    """
                    MATCH path=(affected:Component)-[:DEPENDS_ON*0..5]->(owned:Component {id: $ownedId})
                    RETURN [component IN nodes(path) | component.id] AS reversePath
                    ORDER BY length(path)
                    """,
                    {"ownedId": owned_id},
                )
                for row in dependent_rows:
                    reverse_path = [str(item) for item in row[0]]
                    path = [trigger_id, *reversed(reverse_path)]
                    if len(path) > 1:
                        paths.setdefault(path[-1], path)
        elif trigger["type"] == "milestone":
            blocked_rows = self._query(
                """
                MATCH path=(blocked:Component)<-[:BLOCKS*1..5]-(trigger:Component {id: $triggerId})
                RETURN [component IN nodes(path) | component.id] AS reversePath
                ORDER BY length(path)
                """,
                {"triggerId": trigger_id},
            )
            for row in blocked_rows:
                reverse_path = [str(item) for item in row[0]]
                path = list(reversed(reverse_path))
                if len(path) > 1:
                    paths.setdefault(path[-1], path)
                blocked_id = path[-1] if path else ""
                downstream_rows = self._dependent_rows(blocked_id) if blocked_id else []
                for downstream in downstream_rows:
                    downstream_path = [*path, *downstream[1:]]
                    if len(downstream_path) > 1:
                        paths.setdefault(downstream_path[-1], downstream_path)
        else:
            for path in self._dependent_rows(trigger_id):
                if len(path) > 1:
                    paths.setdefault(path[-1], path)

        return sorted(paths.values(), key=lambda path: (len(path), path[-1]))

    def _dependent_rows(self, trigger_id: str) -> list[list[str]]:
        rows = self._query(
            """
            MATCH path=(affected:Component)-[:DEPENDS_ON*1..5]->(trigger:Component {id: $triggerId})
            RETURN [component IN nodes(path) | component.id] AS reversePath
            ORDER BY length(path)
            """,
            {"triggerId": trigger_id},
        )
        return [
            list(reversed([str(item) for item in row[0]]))
            for row in rows
            if row and row[0]
        ]


class UnavailableGraphStore(GraphStore):
    backend = "falkordb"
    database_connected = False

    def __init__(self, error: str):
        self.error = error
        self.graph_name = GRAPH_NAME

    def get_graph(self) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        raise GraphUnavailable(self.error or "FalkorDB is unavailable.")

    def dependent_paths(self, trigger_id: str) -> list[list[str]]:
        raise GraphUnavailable(self.error or "FalkorDB is unavailable.")
