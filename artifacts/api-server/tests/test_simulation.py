import unittest

from whatif.graph_store import GraphStore
from whatif.simulation import simulate


class DemoSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = GraphStore()

    def test_payment_outage_traverses_two_hops_and_preserves_baseline(self) -> None:
        baseline = self.store.get_graph()

        result = simulate(
            "What happens if the Payment Service goes down?",
            self.store,
            client=None,
        )

        affected = {node["id"] for node in result["affectedNodes"]}
        self.assertEqual(result["triggerNode"], "payment-service")
        self.assertEqual(result["eventType"], "outage")
        self.assertEqual(affected, {"order-service", "notification-service"})
        self.assertEqual(result["analysisMode"], "rule_based")
        self.assertEqual(self.store.get_graph(), baseline)

    def test_database_delay_reports_multi_hop_paths_and_heuristics(self) -> None:
        result = simulate(
            "What if the database is delayed by two days?",
            self.store,
            client=None,
        )

        by_id = {node["id"]: node for node in result["affectedNodes"]}
        self.assertEqual(result["triggerNode"], "database")
        self.assertEqual(result["eventType"], "delay")
        self.assertIn("notification-service", by_id)
        self.assertEqual(
            by_id["notification-service"]["path"],
            ["database", "order-service", "notification-service"],
        )
        self.assertTrue(all(item["basis"] == "heuristic" for item in result["mitigations"]))

    def test_team_capacity_loss_uses_ownership_edges(self) -> None:
        result = simulate(
            "What if the Engineering Team loses one member?",
            self.store,
            client=None,
        )

        affected = {node["id"] for node in result["affectedNodes"]}
        self.assertEqual(result["triggerNode"], "engineering-team")
        self.assertEqual(result["eventType"], "capacity_loss")
        self.assertTrue(
            {"payment-service", "order-service", "inventory-service", "notification-service"}
            <= affected
        )

    def test_inventory_outage_uses_dependency_relationships(self) -> None:
        result = simulate(
            "What if the Inventory Service is unavailable?",
            self.store,
            client=None,
        )

        affected = {node["id"] for node in result["affectedNodes"]}
        self.assertEqual(result["triggerNode"], "inventory-service")
        self.assertEqual(affected, {"order-service", "notification-service"})

    def test_unrecognized_scenario_fails_with_component_guidance(self) -> None:
        with self.assertRaisesRegex(ValueError, "Couldn't identify a component"):
            simulate("Something unrelated might change", self.store, client=None)


if __name__ == "__main__":
    unittest.main()
