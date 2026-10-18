import os
import re
from typing import Dict, Optional
from lib.logger import logger


# Component name to ID mapping
COMPONENT_MAP = {
    "payment service": "payment_service",
    "payment": "payment_service",
    "order service": "order_service",
    "order": "order_service",
    "inventory service": "inventory_service",
    "inventory": "inventory_service",
    "notification service": "notification_service",
    "notification": "notification_service",
    "primary database": "primary_database",
    "database": "primary_database",
    "message queue": "message_queue",
    "queue": "message_queue",
    "engineering team": "engineering_team",
    "team": "engineering_team",
    "deployment deadline": "deployment_deadline",
    "deadline": "deployment_deadline",
}

# Event type patterns
EVENT_PATTERNS = {
    "outage": r"(goes down|outage|fail|unavailable|down|crash)",
    "delay": r"(delay|delayed|slow|slower)",
    "capacity_loss": r"(lose.*member|capacity|resource|staffing)",
}


def parse_scenario(scenario: str, ai_configured: bool) -> Dict:
    """
    Parse a natural language scenario into a node ID and event type.
    Uses AI if configured, otherwise falls back to rule-based parsing.
    """
    if ai_configured and os.environ.get("OPENAI_API_KEY"):
        try:
            return parse_with_ai(scenario)
        except Exception as e:
            logger.warning(f"AI parsing failed, falling back to rule-based: {e}")

    return parse_with_rules(scenario)


def parse_with_ai(scenario: str) -> Dict:
    """Parse scenario using OpenAI API."""
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
        )

        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        component_list = ", ".join(COMPONENT_MAP.keys())

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a scenario parser for a dependency graph simulator.
Extract the target component and event type from the user's scenario.

Available components: {component_list}
Event types: outage, delay, capacity_loss

Return JSON with exactly these fields:
- node_id: the exact component ID from this list: {list(COMPONENT_MAP.values())}
- event_type: one of "outage", "delay", "capacity_loss"
- ai_used: true"""
                },
                {
                    "role": "user",
                    "content": scenario
                }
            ],
            response_format={"type": "json_object"}
        )

        import json
        result = json.loads(response.choices[0].message.content)
        result["ai_used"] = True
        return result

    except Exception as e:
        logger.error(f"AI parsing error: {e}")
        raise ValueError("AI parsing failed, please try a simpler scenario")


def parse_with_rules(scenario: str) -> Dict:
    """Parse scenario using rule-based pattern matching."""
    scenario_lower = scenario.lower()

    # Find matching component
    matched_component = None
    for name, id in COMPONENT_MAP.items():
        if name in scenario_lower:
            matched_component = id
            break

    if not matched_component:
        raise ValueError(
            f"Could not identify target component. Available components: {', '.join(COMPONENT_MAP.keys())}"
        )

    # Find matching event type
    matched_event = None
    for event_type, pattern in EVENT_PATTERNS.items():
        if re.search(pattern, scenario_lower):
            matched_event = event_type
            break

    if not matched_event:
        # Default to outage if no specific event pattern matches
        matched_event = "outage"

    return {
        "node_id": matched_component,
        "event_type": matched_event,
        "ai_used": False
    }
