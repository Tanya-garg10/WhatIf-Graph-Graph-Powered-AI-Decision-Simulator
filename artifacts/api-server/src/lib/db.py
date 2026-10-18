import os
from typing import Optional, Tuple
import falkordb
from falkordb import Graph
from lib.logger import logger


# Configuration
FALKORDB_URI = os.environ.get("FALKORDB_URI") or os.environ.get("FALKORDB_URL")
FALKORDB_HOST = os.environ.get("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.environ.get("FALKORDB_PORT", "6379"))
FALKORDB_USERNAME = os.environ.get("FALKORDB_USERNAME")
FALKORDB_PASSWORD = os.environ.get("FALKORDB_PASSWORD")
FALKORDB_SSL = os.environ.get("FALKORDB_SSL", "false").lower() == "true"
FALKORDB_GRAPH_NAME = os.environ.get("FALKORDB_GRAPH_NAME", "whatif_graph")
FALKORDB_CONNECT_TIMEOUT = int(os.environ.get("FALKORDB_CONNECT_TIMEOUT", "4"))

# Global connection and graph
client: Optional[falkordb.FalkorDB] = None
graph: Optional[Graph] = None
is_demo_mode = False


def get_connection() -> Tuple[Optional[falkordb.FalkorDB], Optional[Graph], bool]:
    """Get database connection and graph. Returns (client, graph, is_demo_mode)."""
    global client, graph, is_demo_mode

    if client is not None and graph is not None:
        return client, graph, is_demo_mode

    # Try to connect to FalkorDB
    if FALKORDB_URI:
        try:
            logger.info(f"Connecting to FalkorDB via URI: {FALKORDB_URI[:20]}...")
            client = falkordb.FalkorDB(url=FALKORDB_URI)
            graph = client.select_graph(FALKORDB_GRAPH_NAME)
            is_demo_mode = False
            logger.info("Connected to FalkorDB via URI")
            return client, graph, is_demo_mode
        except Exception as e:
            logger.warning(f"Failed to connect via URI: {e}")
            client = None
            graph = None

    # Try field-based connection
    if FALKORDB_HOST and not is_demo_mode:
        try:
            logger.info(f"Connecting to FalkorDB at {FALKORDB_HOST}:{FALKORDB_PORT}...")
            client = falkordb.FalkorDB(
                host=FALKORDB_HOST,
                port=FALKORDB_PORT,
                username=FALKORDB_USERNAME,
                password=FALKORDB_PASSWORD,
                ssl=FALKORDB_SSL,
            )
            graph = client.select_graph(FALKORDB_GRAPH_NAME)
            is_demo_mode = False
            logger.info("Connected to FalkorDB via field-based config")
            return client, graph, is_demo_mode
        except Exception as e:
            logger.warning(f"Failed to connect via field-based config: {e}")
            client = None
            graph = None

    # Fall back to demo mode
    logger.info("No FalkorDB connection available, using demo mode")
    is_demo_mode = True
    return None, None, is_demo_mode


async def health_check() -> bool:
    """Test database connection health."""
    client, graph, is_demo = get_connection()
    if is_demo:
        return True  # Demo mode is always "healthy"
    try:
        if client and graph:
            # Simple query to test connection
            result = graph.query("MATCH (n) RETURN count(n) LIMIT 1")
            return True
        return False
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False


async def initialize_database():
    """Initialize the database with sample data if empty."""
    client, graph, is_demo = get_connection()

    if is_demo:
        logger.info("Demo mode: skipping database initialization")
        return

    try:
        # Check if graph already has data
        result = graph.query("MATCH (n:Component) RETURN count(n) AS count")
        count = int(result.result_set[0][0]) if result.result_set else 0

        if count > 0:
            logger.info(f"Graph already has {count} components, skipping seed")
            return

        logger.info("Graph is empty, seeding with sample data...")
        seed_sample_graph(graph)
        logger.info("Sample graph seeded successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Continue in demo mode if seeding fails
        global is_demo_mode
        is_demo_mode = True


def seed_sample_graph(graph: Graph):
    """Seed the graph with sample e-commerce components."""
    # Create nodes
    components = [
        ("payment_service", "Payment Service", "service", "Processes payment transactions", "operational"),
        ("order_service", "Order Service", "service", "Manages order lifecycle", "operational"),
        ("inventory_service", "Inventory Service", "service", "Manages product inventory", "operational"),
        ("notification_service", "Notification Service", "service", "Sends user notifications", "operational"),
        ("primary_database", "Primary Database", "database", "Main data store", "operational"),
        ("message_queue", "Message Queue", "infrastructure", "Async message broker", "operational"),
        ("engineering_team", "Engineering Team", "team", "Development team", "operational"),
        ("deployment_deadline", "Deployment Deadline", "deadline", "Production release milestone", "upcoming"),
    ]

    for comp_id, name, comp_type, description, status in components:
        graph.query(
            """
            MERGE (c:Component {id: $id})
            SET c.name = $name, c.type = $type, c.description = $description, c.status = $status
            """,
            {"id": comp_id, "name": name, "type": comp_type, "description": description, "status": status}
        )

    # Create relationships - DEPENDS_ON
    dependencies = [
        ("order_service", "payment_service"),
        ("order_service", "inventory_service"),
        ("notification_service", "message_queue"),
        ("payment_service", "primary_database"),
        ("inventory_service", "primary_database"),
    ]

    for source, target in dependencies:
        graph.query(
            """
            MATCH (s:Component {id: $source}), (t:Component {id: $target})
            MERGE (s)-[:DEPENDS_ON]->(t)
            """,
            {"source": source, "target": target}
        )

    # Create relationships - OWNED_BY
    ownerships = [
        ("payment_service", "engineering_team"),
        ("order_service", "engineering_team"),
        ("inventory_service", "engineering_team"),
        ("notification_service", "engineering_team"),
    ]

    for component, team in ownerships:
        graph.query(
            """
            MATCH (c:Component {id: $component}), (t:Component {id: $team})
            MERGE (c)-[:OWNED_BY]->(t)
            """,
            {"component": component, "team": team}
        )

    # Create relationships - BLOCKS
    blocks = [
        ("deployment_deadline", "payment_service"),
        ("deployment_deadline", "order_service"),
    ]

    for deadline, component in blocks:
        graph.query(
            """
            MATCH (d:Component {id: $deadline}), (c:Component {id: $component})
            MERGE (d)-[:BLOCKS]->(c)
            """,
            {"deadline": deadline, "component": component}
        )
