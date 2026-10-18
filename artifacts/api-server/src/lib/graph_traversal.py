from typing import Dict, List, Any
from lib.logger import logger


def compute_impact(
    trigger_node: str,
    event_type: str,
    nodes: List[Dict],
    edges: List[Dict],
    graph: Any = None,
    is_demo: bool = False
) -> Dict:
    """
    Compute the impact of a scenario on the dependency graph.
    Uses Cypher queries if FalkorDB is available, otherwise uses local traversal.
    """
    if not is_demo and graph:
        return compute_impact_with_cypher(trigger_node, event_type, graph, nodes)
    else:
        return compute_impact_local(trigger_node, event_type, nodes, edges)


def compute_impact_with_cypher(trigger_node: str, event_type: str, graph: Any, nodes: List[Dict]) -> Dict:
    """Compute impact using Cypher queries against FalkorDB."""
    logger.info(f"Computing impact for {trigger_node} ({event_type}) using Cypher")

    # Build adjacency map from nodes
    node_map = {n["id"]: n for n in nodes}

    # For outages: find all components that depend on the trigger (reverse traversal)
    if event_type == "outage":
        query = """
        MATCH path=(affected:Component)-[:DEPENDS_ON*1..5]->(trigger:Component {id: $triggerId})
        RETURN affected.id, affected.name, affected.type, [node IN nodes(path) | node.id] AS path
        """
        result = graph.query(query, {"triggerId": trigger_node})

        affected_nodes = []
        for row in result.result_set:
            node_id, name, node_type, path = row
            # Reverse path to show trigger -> affected
            reversed_path = list(reversed(path))
            severity = calculate_severity(node_type, len(path))
            affected_nodes.append({
                "id": node_id,
                "name": name,
                "type": node_type,
                "severity": severity,
                "reason": f"Depends on {trigger_node} through {len(path)-1} hop(s)",
                "path": reversed_path
            })

    # For delays: similar to outages but with different severity
    elif event_type == "delay":
        query = """
        MATCH path=(affected:Component)-[:DEPENDS_ON*1..5]->(trigger:Component {id: $triggerId})
        RETURN affected.id, affected.name, affected.type, [node IN nodes(path) | node.id] AS path
        """
        result = graph.query(query, {"triggerId": trigger_node})

        affected_nodes = []
        for row in result.result_set:
            node_id, name, node_type, path = row
            reversed_path = list(reversed(path))
            severity = calculate_severity(node_type, len(path), base_reduction=1)
            affected_nodes.append({
                "id": node_id,
                "name": name,
                "type": node_type,
                "severity": severity,
                "reason": f"Delayed by {trigger_node} through {len(path)-1} hop(s)",
                "path": reversed_path
            })

    # For capacity loss: find components owned by the team, then their dependents
    elif event_type == "capacity_loss":
        # First, find components owned by this team
        owned_query = """
        MATCH (owned:Component)-[:OWNED_BY]->(team:Component {id: $triggerId})
        RETURN owned.id, owned.name, owned.type
        """
        owned_result = graph.query(owned_query, {"triggerId": trigger_node})

        owned_ids = [row[0] for row in owned_result.result_set]

        # Then find dependents of owned components
        affected_nodes = []
        for owned_id in owned_ids:
            query = """
            MATCH path=(affected:Component)-[:DEPENDS_ON*1..5]->(owned:Component {id: $ownedId})
            RETURN affected.id, affected.name, affected.type, [node IN nodes(path) | node.id] AS path
            """
            result = graph.query(query, {"ownedId": owned_id})

            for row in result.result_set:
                node_id, name, node_type, path = row
                reversed_path = list(reversed(path))
                severity = calculate_severity(node_type, len(path), base_reduction=1)
                affected_nodes.append({
                    "id": node_id,
                    "name": name,
                    "type": node_type,
                    "severity": severity,
                    "reason": f"Depends on {owned_id} (owned by {trigger_node})",
                    "path": reversed_path
                })

        # Also add the owned components themselves
        for row in owned_result.result_set:
            node_id, name, node_type = row
            affected_nodes.append({
                "id": node_id,
                "name": name,
                "type": node_type,
                "severity": "high",
                "reason": f"Directly owned by {trigger_node}",
                "path": [trigger_node, node_id]
            })

    else:
        raise ValueError(f"Unsupported event type: {event_type}")

    # Calculate overall risk
    risk = calculate_overall_risk(affected_nodes, len(nodes))

    # Generate mitigations
    mitigations = generate_mitigations(trigger_node, event_type, affected_nodes)

    # Identify bottlenecks
    bottlenecks = identify_bottlenecks(affected_nodes)

    return {
        "affected_nodes": affected_nodes,
        "risk": risk,
        "bottlenecks": bottlenecks,
        "mitigations": mitigations,
        "explanation": generate_explanation(trigger_node, event_type, affected_nodes, risk)
    }


def compute_impact_local(trigger_node: str, event_type: str, nodes: List[Dict], edges: List[Dict]) -> Dict:
    """Compute impact using local graph traversal (demo mode)."""
    logger.info(f"Computing impact for {trigger_node} ({event_type}) using local traversal")

    # Build adjacency map
    adjacency = {}
    for edge in edges:
        if edge["relationship"] == "DEPENDS_ON":
            source = edge["source"]
            target = edge["target"]
            if target not in adjacency:
                adjacency[target] = []
            adjacency[target].append(source)

    # Node map
    node_map = {n["id"]: n for n in nodes}

    # BFS to find affected nodes
    affected_nodes = []
    visited = set()

    def dfs(node_id: str, path: List[str], depth: int = 0):
        if node_id in visited or depth > 5:
            return
        visited.add(node_id)

        if node_id != trigger_node:
            node = node_map.get(node_id)
            if node:
                severity = calculate_severity(node["type"], len(path))
                affected_nodes.append({
                    "id": node_id,
                    "name": node["name"],
                    "type": node["type"],
                    "severity": severity,
                    "reason": f"Depends on {trigger_node} through {len(path)-1} hop(s)",
                    "path": path.copy()
                })

        # Traverse dependents
        for dependent in adjacency.get(node_id, []):
            new_path = path.copy()
            new_path.append(dependent)
            dfs(dependent, new_path, depth + 1)

    # Start traversal
    if event_type == "capacity_loss":
        # For team capacity loss, find owned components first
        owned_components = []
        for edge in edges:
            if edge["relationship"] == "OWNED_BY" and edge["target"] == trigger_node:
                owned_components.append(edge["source"])

        # Add owned components as affected
        for owned_id in owned_components:
            node = node_map.get(owned_id)
            if node:
                affected_nodes.append({
                    "id": owned_id,
                    "name": node["name"],
                    "type": node["type"],
                    "severity": "high",
                    "reason": f"Directly owned by {trigger_node}",
                    "path": [trigger_node, owned_id]
                })

        # Then traverse dependents of owned components
        for owned_id in owned_components:
            dfs(owned_id, [trigger_node, owned_id])
    else:
        dfs(trigger_node, [trigger_node])

    # Calculate overall risk
    risk = calculate_overall_risk(affected_nodes, len(nodes))

    # Generate mitigations
    mitigations = generate_mitigations(trigger_node, event_type, affected_nodes)

    # Identify bottlenecks
    bottlenecks = identify_bottlenecks(affected_nodes)

    return {
        "affected_nodes": affected_nodes,
        "risk": risk,
        "bottlenecks": bottlenecks,
        "mitigations": mitigations,
        "explanation": generate_explanation(trigger_node, event_type, affected_nodes, risk)
    }


def calculate_severity(node_type: str, path_length: int, base_reduction: int = 0) -> str:
    """Calculate severity based on node type and dependency distance."""
    # Base severity by type
    type_severity = {
        "database": 4,
        "service": 3,
        "infrastructure": 3,
        "team": 2,
        "deadline": 1,
    }

    base = type_severity.get(node_type, 2)

    # Reduce severity with distance
    adjusted = max(1, base - (path_length - 1) - base_reduction)

    if adjusted >= 4:
        return "critical"
    elif adjusted == 3:
        return "high"
    elif adjusted == 2:
        return "medium"
    else:
        return "low"


def calculate_overall_risk(affected_nodes: List[Dict], total_nodes: int) -> str:
    """Calculate overall risk level based on affected nodes."""
    if not affected_nodes:
        return "low"

    critical_count = sum(1 for n in affected_nodes if n["severity"] == "critical")
    high_count = sum(1 for n in affected_nodes if n["severity"] == "high")

    affected_ratio = len(affected_nodes) / max(total_nodes, 1)

    if critical_count > 0 or (high_count >= 2 and affected_ratio > 0.5):
        return "critical"
    elif high_count > 0 or affected_ratio > 0.4:
        return "high"
    elif affected_ratio > 0.2:
        return "moderate"
    else:
        return "low"


def identify_bottlenecks(affected_nodes: List[Dict]) -> List[str]:
    """Identify potential bottlenecks based on affected nodes."""
    bottlenecks = []

    # Count how many nodes depend on each affected node
    dependency_counts = {}
    for node in affected_nodes:
        node_id = node["id"]
        dependency_counts[node_id] = dependency_counts.get(node_id, 0) + 1

    # Find nodes with high dependency count
    for node_id, count in sorted(dependency_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= 2:
            node_name = next((n["name"] for n in affected_nodes if n["id"] == node_id), node_id)
            bottlenecks.append(f"{node_name} (affects {count} components)")

    return bottlenecks[:5]  # Return top 5


def generate_mitigations(trigger_node: str, event_type: str, affected_nodes: List[Dict]) -> List[Dict]:
    """Generate heuristic mitigation suggestions."""
    mitigations = []

    # Generic mitigations based on event type
    if event_type == "outage":
        mitigations.append({
            "title": "Implement circuit breaker pattern",
            "detail": "Add circuit breakers to prevent cascading failures when dependencies are unavailable.",
            "basis": "heuristic"
        })
        mitigations.append({
            "title": "Enable retry with exponential backoff",
            "detail": "Configure retry logic for transient failures to improve resilience.",
            "basis": "heuristic"
        })
    elif event_type == "delay":
        mitigations.append({
            "title": "Add caching layer",
            "detail": "Cache responses to reduce dependency on slow components.",
            "basis": "heuristic"
        })
        mitigations.append({
            "title": "Implement timeout policies",
            "detail": "Set appropriate timeouts to prevent indefinite waiting.",
            "basis": "heuristic"
        })
    elif event_type == "capacity_loss":
        mitigations.append({
            "title": "Prioritize critical work",
            "detail": "Focus remaining capacity on high-priority tasks and defer non-critical work.",
            "basis": "heuristic"
        })
        mitigations.append({
            "title": "Request additional resources",
            "detail": "Escalate to management for temporary resource allocation.",
            "basis": "heuristic"
        })

    # Add specific mitigations for critical nodes
    critical_nodes = [n for n in affected_nodes if n["severity"] == "critical"]
    if critical_nodes:
        mitigations.append({
            "title": "Add redundancy for critical components",
            "detail": f"Consider adding failover capacity for {len(critical_nodes)} critical affected components.",
            "basis": "heuristic"
        })

    return mitigations[:6]  # Return top 6


def generate_explanation(trigger_node: str, event_type: str, affected_nodes: List[Dict], risk: str) -> str:
    """Generate a human-readable explanation of the impact."""
    if not affected_nodes:
        return f"No components are directly affected by {event_type} of {trigger_node}."

    critical_count = sum(1 for n in affected_nodes if n["severity"] == "critical")
    high_count = sum(1 for n in affected_nodes if n["severity"] == "high")

    explanation = f"If {trigger_node} experiences {event_type}, "
    explanation += f"{len(affected_nodes)} component(s) would be affected. "

    if critical_count > 0:
        explanation += f"{critical_count} critical component(s) would be impacted. "
    if high_count > 0:
        explanation += f"{high_count} high-severity impact(s) identified. "

    explanation += f"Overall risk level: {risk}. "

    explanation += "This is a simulation based on graph dependencies and does not account for real-time telemetry or external factors."

    return explanation
