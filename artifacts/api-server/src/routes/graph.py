from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import os
from lib.db import get_connection, seed_sample_graph
from lib.logger import logger
from lib.scenario_parser import parse_scenario
from lib.graph_traversal import compute_impact

router = APIRouter(prefix="/api")


# Pydantic models matching OpenAPI spec
class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    description: str
    status: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    backend: Literal["falkordb", "demo"]
    databaseConnected: bool
    aiConfigured: bool
    graphName: str


class ScenarioInput(BaseModel):
    scenario: str = Field(..., min_length=5, max_length=500)


class ImpactNode(BaseModel):
    id: str
    name: str
    type: str
    severity: Literal["critical", "high", "medium", "low"]
    reason: str
    path: List[str]


class Mitigation(BaseModel):
    title: str
    detail: str
    basis: Literal["heuristic"]


class SimulationResponse(BaseModel):
    scenario: str
    triggerNode: str
    eventType: Literal["outage", "delay", "capacity_loss"]
    risk: Literal["critical", "high", "moderate", "low"]
    baselineComponentCount: int
    affectedComponentCount: int
    affectedNodes: List[ImpactNode]
    bottlenecks: List[str]
    mitigations: List[Mitigation]
    explanation: str
    backend: Literal["falkordb", "demo"]
    databaseConnected: bool
    analysisMode: Literal["ai_assisted", "rule_based"]


@router.get("/graph", response_model=GraphResponse)
async def get_graph():
    """Get the baseline dependency graph."""
    client, graph, is_demo = get_connection()

    ai_configured = bool(os.environ.get("OPENAI_API_KEY"))

    if is_demo:
        # Return demo graph
        nodes_data, edges_data = get_demo_graph()
        nodes = [node.model_dump() for node in nodes_data]
        edges = [edge.model_dump() for edge in edges_data]
        return GraphResponse(
            nodes=nodes_data,
            edges=edges_data,
            backend="demo",
            databaseConnected=False,
            aiConfigured=ai_configured,
            graphName="demo"
        )

    try:
        # Query nodes from FalkorDB
        result = graph.query("MATCH (n:Component) RETURN n.id, n.name, n.type, n.description, n.status")
        nodes = [
            GraphNode(
                id=row[0],
                name=row[1],
                type=row[2],
                description=row[3],
                status=row[4]
            )
            for row in result.result_set
        ]

        # Query edges from FalkorDB
        edges = []
        for rel_type in ["DEPENDS_ON", "OWNED_BY", "BLOCKS"]:
            result = graph.query(
                f"MATCH (a:Component)-[r:{rel_type}]->(b:Component) RETURN a.id, b.id, '{rel_type}'"
            )
            for row in result.result_set:
                edges.append(GraphEdge(source=row[0], target=row[1], relationship=row[2]))

        return GraphResponse(
            nodes=nodes,
            edges=edges,
            backend="falkordb",
            databaseConnected=True,
            aiConfigured=ai_configured,
            graphName=os.environ.get("FALKORDB_GRAPH_NAME", "whatif_graph")
        )
    except Exception as e:
        logger.error(f"Error fetching graph: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch graph")


@router.post("/seed")
async def seed_graph():
    """Seed the graph with sample data."""
    client, graph_instance, is_demo = get_connection()

    if is_demo:
        raise HTTPException(status_code=400, detail="Cannot seed graph in demo mode")

    try:
        from lib.db import seed_sample_graph
        seed_sample_graph(graph_instance)
        return {"message": "Graph seeded successfully"}
    except Exception as e:
        logger.error(f"Error seeding graph: {e}")
        raise HTTPException(status_code=500, detail="Failed to seed graph")


@router.get("/scenarios")
async def get_scenarios():
    """Get available example scenarios."""
    scenarios = [
        {
            "id": "payment_outage",
            "text": "What happens if Payment Service goes down?",
            "description": "Simulates a complete outage of the payment processing service"
        },
        {
            "id": "database_outage",
            "text": "What happens if the Primary Database becomes unavailable?",
            "description": "Simulates database failure affecting all dependent services"
        },
        {
            "id": "inventory_delay",
            "text": "What if Inventory Service is delayed by two days?",
            "description": "Simulates performance degradation of inventory management"
        },
        {
            "id": "team_capacity",
            "text": "What if the Engineering Team loses one member?",
            "description": "Simulates reduced team capacity affecting owned services"
        },
        {
            "id": "queue_failure",
            "text": "What happens if Message Queue fails?",
            "description": "Simulates message broker failure affecting async operations"
        }
    ]
    return {"scenarios": scenarios}


@router.post("/simulate", response_model=SimulationResponse)
async def simulate_scenario(input: ScenarioInput):
    """Simulate a hypothetical system change."""
    client, graph_instance, is_demo = get_connection()

    ai_configured = bool(os.environ.get("OPENAI_API_KEY"))

    # Parse the scenario
    try:
        parsed = parse_scenario(input.scenario, ai_configured)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get baseline graph data
    if is_demo:
        nodes_data, edges_data = get_demo_graph()
        nodes = [node.model_dump() for node in nodes_data]
        edges = [edge.model_dump() for edge in edges_data]
    else:
        try:
            result = graph_instance.query("MATCH (n:Component) RETURN n.id, n.name, n.type, n.description, n.status")
            nodes = [
                {
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "description": row[3],
                    "status": row[4]
                }
                for row in result.result_set
            ]
            edges = []
            for rel_type in ["DEPENDS_ON", "OWNED_BY", "BLOCKS"]:
                result = graph_instance.query(
                    f"MATCH (a:Component)-[r:{rel_type}]->(b:Component) RETURN a.id, b.id"
                )
                for row in result.result_set:
                    edges.append({"source": row[0], "target": row[1], "relationship": rel_type})
        except Exception as e:
            logger.error(f"Error fetching graph for simulation: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch graph for simulation")

    # Compute impact
    try:
        impact = compute_impact(
            trigger_node=parsed["node_id"],
            event_type=parsed["event_type"],
            nodes=nodes,
            edges=edges,
            graph=graph_instance if not is_demo else None,
            is_demo=is_demo
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SimulationResponse(
        scenario=input.scenario,
        triggerNode=parsed["node_id"],
        eventType=parsed["event_type"],
        risk=impact["risk"],
        baselineComponentCount=len(nodes),
        affectedComponentCount=len(impact["affected_nodes"]),
        affectedNodes=impact["affected_nodes"],
        bottlenecks=impact["bottlenecks"],
        mitigations=impact["mitigations"],
        explanation=impact["explanation"],
        backend="demo" if is_demo else "falkordb",
        databaseConnected=not is_demo,
        analysisMode="ai_assisted" if parsed.get("ai_used") else "rule_based"
    )


def get_demo_graph():
    """Return the demo graph data."""
    nodes = [
        GraphNode(id="payment_service", name="Payment Service", type="service", description="Processes payment transactions", status="operational"),
        GraphNode(id="order_service", name="Order Service", type="service", description="Manages order lifecycle", status="operational"),
        GraphNode(id="inventory_service", name="Inventory Service", type="service", description="Manages product inventory", status="operational"),
        GraphNode(id="notification_service", name="Notification Service", type="service", description="Sends user notifications", status="operational"),
        GraphNode(id="primary_database", name="Primary Database", type="database", description="Main data store", status="operational"),
        GraphNode(id="message_queue", name="Message Queue", type="infrastructure", description="Async message broker", status="operational"),
        GraphNode(id="engineering_team", name="Engineering Team", type="team", description="Development team", status="operational"),
        GraphNode(id="deployment_deadline", name="Deployment Deadline", type="deadline", description="Production release milestone", status="upcoming"),
    ]

    edges = [
        GraphEdge(source="order_service", target="payment_service", relationship="DEPENDS_ON"),
        GraphEdge(source="order_service", target="inventory_service", relationship="DEPENDS_ON"),
        GraphEdge(source="notification_service", target="message_queue", relationship="DEPENDS_ON"),
        GraphEdge(source="payment_service", target="primary_database", relationship="DEPENDS_ON"),
        GraphEdge(source="inventory_service", target="primary_database", relationship="DEPENDS_ON"),
        GraphEdge(source="payment_service", target="engineering_team", relationship="OWNED_BY"),
        GraphEdge(source="order_service", target="engineering_team", relationship="OWNED_BY"),
        GraphEdge(source="inventory_service", target="engineering_team", relationship="OWNED_BY"),
        GraphEdge(source="notification_service", target="engineering_team", relationship="OWNED_BY"),
        GraphEdge(source="deployment_deadline", target="payment_service", relationship="BLOCKS"),
        GraphEdge(source="deployment_deadline", target="order_service", relationship="BLOCKS"),
    ]

    return nodes, edges
