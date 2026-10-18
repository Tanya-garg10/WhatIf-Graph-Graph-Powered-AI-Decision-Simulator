from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from .graph_store import GraphStore

NODE_ALIASES: dict[str, tuple[str, ...]] = {
    "payment-service": ("payment service", "payment", "payments", "checkout"),
    "order-service": ("order service", "order", "orders", "ordering"),
    "inventory-service": ("inventory service", "inventory", "stock"),
    "notification-service": ("notification service", "notifications", "notification", "alerts"),
    "database": ("database", "data store", "datastore", " db ", "db"),
    "engineering-team": ("engineering team", "engineering", "engineer", "developers", "team member", "team"),
    "deployment-deadline": ("deployment deadline", "release deadline", "deadline", "deployment"),
}

EVENT_TERMS: dict[str, tuple[str, ...]] = {
    "capacity_loss": ("loses", "lose", "lost", "member", "capacity", "headcount", "team"),
    "delay": ("delay", "delayed", "late", "slip", "postpone", "two days", "days", "week"),
    "outage": ("down", "unavailable", "outage", "failure", "failed", "offline", "goes down"),
}


def _normalize(value: str) -> str:
    return f" {re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()} "


def parse_scenario_rules(scenario: str, nodes: list[dict[str, str]]) -> tuple[str | None, str]:
    normalized = _normalize(scenario)
    node_ids = {node["id"] for node in nodes}
    matches: list[tuple[int, str]] = []
    for node_id, aliases in NODE_ALIASES.items():
        if node_id not in node_ids:
            continue
        for alias in aliases:
            term = _normalize(alias)
            if term.strip() and term in normalized:
                matches.append((len(term), node_id))
    trigger_id = max(matches, default=(0, None), key=lambda match: match[0])[1]

    event_type = "outage"
    if any(term in normalized for term in EVENT_TERMS["capacity_loss"]):
        event_type = "capacity_loss"
    elif any(term in normalized for term in EVENT_TERMS["delay"]):
        event_type = "delay"
    return trigger_id, event_type


def _openai_client() -> OpenAI | None:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    options: dict[str, Any] = {"api_key": key}
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        options["base_url"] = base_url
    return OpenAI(**options)


def interpret_scenario(
    scenario: str,
    nodes: list[dict[str, str]],
    client: OpenAI | None,
) -> tuple[str | None, str, str]:
    rule_node, rule_event = parse_scenario_rules(scenario, nodes)
    if client is None:
        return rule_node, rule_event, "rule_based"

    try:
        choices = [
            {"id": node["id"], "name": node["name"], "type": node["type"]}
            for node in nodes
        ]
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-nano"),
            response_format={"type": "json_object"},
            max_completion_tokens=8192,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Map one hypothetical software-system scenario to exactly one supplied component and "
                        "one event type. Return JSON only with keys nodeId and eventType. eventType must be "
                        "outage, delay, or capacity_loss. Use nodeId null if no component clearly matches. "
                        "Do not calculate impacts or invent components."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"scenario": scenario, "components": choices}),
                },
            ],
        )
        content = response.choices[0].message.content
        parsed = json.loads(content or "{}")
        candidate_id = parsed.get("nodeId")
        candidate_event = parsed.get("eventType")
        allowed_ids = {node["id"] for node in nodes}
        allowed_events = {"outage", "delay", "capacity_loss"}
        if candidate_id in allowed_ids and candidate_event in allowed_events:
            return candidate_id, candidate_event, "ai_assisted"
    except Exception:
        # AI interpretation is optional; graph traversal still runs deterministically.
        pass
    return rule_node, rule_event, "rule_based"


def _severity(event_type: str, trigger_id: str, node: dict[str, str], path: list[str]) -> str:
    if event_type == "capacity_loss":
        if len(path) <= 2:
            return "medium"
        return "low"
    if node["id"] in {"order-service", "payment-service"} and len(path) <= 3:
        return "high"
    if node["id"] == "database":
        return "critical"
    if len(path) <= 2:
        return "high"
    if len(path) <= 4:
        return "medium"
    return "low"


def _mitigations(trigger_id: str, event_type: str) -> list[dict[str, str]]:
    if event_type == "capacity_loss":
        return [
            {
                "title": "Protect the highest-impact ownership paths",
                "detail": "Temporarily assign a named backup owner to each directly affected service.",
                "basis": "heuristic",
            },
            {
                "title": "Reduce concurrent change load",
                "detail": "Defer non-critical releases until engineering capacity returns.",
                "basis": "heuristic",
            },
        ]
    if event_type == "delay":
        return [
            {
                "title": "Re-sequence dependent work",
                "detail": "Keep changes that rely on this component behind a readiness gate.",
                "basis": "heuristic",
            },
            {
                "title": "Protect the release window",
                "detail": "Publish a revised milestone and confirm downstream teams can absorb the shift.",
                "basis": "heuristic",
            },
        ]
    if trigger_id == "database":
        return [
            {
                "title": "Fail over to a healthy replica",
                "detail": "Verify replica freshness and promote through the documented recovery procedure.",
                "basis": "heuristic",
            },
            {
                "title": "Queue writes safely",
                "detail": "Apply backpressure and replay idempotent writes after storage recovers.",
                "basis": "heuristic",
            },
        ]
    if trigger_id == "payment-service":
        return [
            {
                "title": "Route checkout to a backup processor",
                "detail": "Enable the approved alternate payment route and reconcile duplicate captures.",
                "basis": "heuristic",
            },
            {
                "title": "Stop retry amplification",
                "detail": "Use a circuit breaker and bounded retries while payment authorization is degraded.",
                "basis": "heuristic",
            },
        ]
    if trigger_id == "inventory-service":
        return [
            {
                "title": "Guard stock reservations",
                "detail": "Use a short-lived availability snapshot and avoid promising unverified stock.",
                "basis": "heuristic",
            },
            {
                "title": "Reconcile queued order updates",
                "detail": "Record reservation changes for replay when inventory is available again.",
                "basis": "heuristic",
            },
        ]
    return [
        {
            "title": "Isolate the affected dependency",
            "detail": "Use a circuit breaker or maintenance gate to limit propagation while the component recovers.",
            "basis": "heuristic",
        },
        {
            "title": "Confirm downstream recovery",
            "detail": "Reconcile queued work and verify each dependent service before restoring normal traffic.",
            "basis": "heuristic",
        },
    ]


def simulate(
    scenario: str,
    store: GraphStore,
    client: OpenAI | None,
) -> dict[str, Any]:
    nodes, edges = store.get_graph()
    by_id = {node["id"]: node for node in nodes}
    trigger_id, event_type, analysis_mode = interpret_scenario(scenario, nodes, client)
    if not trigger_id or trigger_id not in by_id:
        available = ", ".join(node["name"] for node in nodes)
        raise ValueError(
            f"Couldn't identify a component in that scenario. Try one of: {available}."
        )

    paths = store.dependent_paths(trigger_id)
    affected: list[dict[str, Any]] = []
    for path in paths:
        node_id = path[-1]
        node = by_id.get(node_id)
        if not node or node_id == trigger_id:
            continue
        named_path = [by_id[item]["name"] for item in path if item in by_id]
        if len(path) > 1 and path[0] == "engineering-team":
            reason = f"Owned capacity is reduced along this graph path: {' → '.join(named_path)}."
        elif len(path) > 1 and path[0] == "deployment-deadline":
            reason = f"The deadline blocks this component along this graph path: {' → '.join(named_path)}."
        else:
            reason = f"Depends on the simulated component along this graph path: {' → '.join(named_path)}."
        affected.append(
            {
                "id": node_id,
                "name": node["name"],
                "type": node["type"],
                "severity": _severity(event_type, trigger_id, node, path),
                "reason": reason,
                "path": path,
            }
        )

    affected.sort(
        key=lambda node: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}[node["severity"]],
            node["name"],
        )
    )

    dependents: dict[str, set[str]] = {}
    for edge in edges:
        if edge["relationship"] == "DEPENDS_ON":
            dependents.setdefault(edge["target"], set()).add(edge["source"])
    candidate_bottlenecks = {trigger_id, *(node["id"] for node in affected)}
    bottlenecks = [
        by_id[node_id]["name"]
        for node_id in candidate_bottlenecks
        if node_id in by_id and len(dependents.get(node_id, set())) >= 2
    ]

    count = len(affected)
    if event_type == "outage" and trigger_id in {"database", "payment-service"}:
        risk = "critical"
    elif event_type == "capacity_loss" and count >= 5:
        risk = "high"
    elif count >= 3:
        risk = "high"
    elif count >= 1:
        risk = "moderate"
    else:
        risk = "low"

    return {
        "scenario": scenario.strip(),
        "triggerNode": trigger_id,
        "eventType": event_type,
        "risk": risk,
        "baselineComponentCount": len(nodes),
        "affectedComponentCount": count,
        "affectedNodes": affected,
        "bottlenecks": bottlenecks,
        "mitigations": _mitigations(trigger_id, event_type),
        "explanation": (
            f"Graph traversal found {count} downstream component"
            f"{'' if count == 1 else 's'} affected by {by_id[trigger_id]['name']}. "
            "The baseline graph was not modified; mitigation steps are heuristic recommendations."
        ),
        "backend": store.backend,
        "databaseConnected": store.database_connected,
        "analysisMode": analysis_mode,
    }
