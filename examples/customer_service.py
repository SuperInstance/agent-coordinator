"""
Customer Service Team Scenario - Tiered support coordination.

This example demonstrates coordinating a customer service team with:
- Tier 1: General support, password resets, basic issues
- Tier 2: Technical support, billing issues
- Tier 3: Escalations, management review
"""

import asyncio
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from agent_coordinator import (
    AgentCoordinator,
    AgentRole,
    Task,
    TaskPriority,
    create_task,
)


@dataclass
class Ticket:
    """Represents a customer support ticket."""
    id: str
    customer: str
    category: str
    priority: str  # low, medium, high, urgent
    description: str
    tier_needed: int = 1
    created_at: datetime = None
    assigned_to: Optional[str] = None
    status: str = "open"  # open, assigned, resolved, escalated
    resolution: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class SLA:
    """Service Level Agreement for ticket categories."""
    category: str
    target_response_time: timedelta  # Time to first response
    target_resolution_time: timedelta  # Time to resolution


# Define SLAs
SLAS = {
    "general": SLA("general", timedelta(minutes=5), timedelta(hours=1)),
    "technical": SLA("technical", timedelta(minutes=15), timedelta(hours=4)),
    "billing": SLA("billing", timedelta(minutes=10), timedelta(hours=2)),
    "escalation": SLA("escalation", timedelta(minutes=5), timedelta(hours=1)),
}


class CustomerServiceTeam:
    """
    Customer service team coordination scenario.

    Creates a tiered support team and processes tickets.
    """

    def __init__(self):
        self.coordinator = None
        self.agents: Dict[str, dict] = {}  # agent_id -> agent info
        self.tickets: Dict[str, Ticket] = {}
        self.ticket_counter = 1000
        self.metrics = {
            "total_tickets": 0,
            "resolved": 0,
            "escalated": 0,
            "sla_breached": 0,
        }

    async def setup(self) -> AgentCoordinator:
        """Set up the customer service team."""
        from agent_coordinator import create_coordinator

        self.coordinator = create_coordinator(name="customer-support")
        await self.coordinator.start()

        # Define roles for each tier
        roles = [
            AgentRole(
                name="tier1",
                capabilities=["general", "password-reset", "basic-info", "faq"],
                max_concurrent_tasks=3,
            ),
            AgentRole(
                name="tier2",
                capabilities=["technical", "billing", "account-issue", "investigation"],
                max_concurrent_tasks=2,
            ),
            AgentRole(
                name="tier3",
                capabilities=["escalation", "management", "complex", "legal"],
                max_concurrent_tasks=1,
            ),
        ]

        for role in roles:
            await self.coordinator.register_role(role)

        # Create agents
        tier1_agents = [
            ("alice", ["general", "faq"]),
            ("bob", ["general", "password-reset"]),
            ("carol", ["general", "basic-info"]),
        ]

        tier2_agents = [
            ("david", ["technical", "account-issue"]),
            ("eve", ["billing", "technical"]),
        ]

        tier3_agents = [
            ("frank", ["escalation", "management"]),
        ]

        for name, specialties in tier1_agents:
            await self._add_agent(name, "tier1", specialties)

        for name, specialties in tier2_agents:
            await self._add_agent(name, "tier2", specialties)

        for name, specialties in tier3_agents:
            await self._add_agent(name, "tier3", specialties)

        print("\n📞 Customer Service Team Ready! 📞")
        print(f"  Tier 1: {len([a for a in self.agents.values() if a['tier'] == 1])} agents")
        print(f"  Tier 2: {len([a for a in self.agents.values() if a['tier'] == 2])} agents")
        print(f"  Tier 3: {len([a for a in self.agents.values() if a['tier'] == 3])} agents")

        return self.coordinator

    async def _add_agent(self, name: str, tier: str, specialties: List[str]) -> str:
        """Add an agent to the team."""
        agent_id = f"{tier}-{name}"

        async def task_handler(task):
            return await self._handle_support_task(agent_id, task)

        await self.coordinator.spawn_agent(
            agent_id=agent_id,
            role=tier,
            task_handler=task_handler,
        )

        self.agents[agent_id] = {
            "name": name,
            "tier": int(tier[-1]),
            "specialties": specialties,
            "tickets_handled": 0,
        }

        return agent_id

    async def _handle_support_task(self, agent_id: str, task: Task) -> dict:
        """Handle a support ticket."""
        agent_info = self.agents[agent_id]
        ticket_id = task.payload.get("ticket_id")
        action = task.payload.get("action", "respond")

        agent_info["tickets_handled"] += 1

        # Simulate work
        await asyncio.sleep(random.uniform(0.5, 2.0))

        if action == "respond":
            response = self._generate_response(agent_info, task.payload)
            return {
                "ticket_id": ticket_id,
                "agent_id": agent_id,
                "agent_name": agent_info["name"],
                "action": "responded",
                "response": response,
                "can_resolve": self._can_resolve(agent_info, task.payload),
            }
        elif action == "resolve":
            resolution = self._generate_resolution(agent_info, task.payload)
            return {
                "ticket_id": ticket_id,
                "agent_id": agent_id,
                "agent_name": agent_info["name"],
                "action": "resolved",
                "resolution": resolution,
            }
        elif action == "escalate":
            return {
                "ticket_id": ticket_id,
                "agent_id": agent_id,
                "agent_name": agent_info["name"],
                "action": "escalated",
                "reason": "Issue requires higher tier support",
            }

        return {"ticket_id": ticket_id, "action": "unknown"}

    def _generate_response(self, agent: dict, task_payload: dict) -> str:
        """Generate a response to the customer."""
        category = task_payload.get("category", "general")
        responses = {
            "general": [
                "Thank you for contacting us. I'll be happy to help with that.",
                "I understand your concern. Let me look into that for you.",
                "Thanks for reaching out. I can assist you with this.",
            ],
            "technical": [
                "I've reviewed your technical issue. Let me walk you through some troubleshooting steps.",
                "This looks like a known issue. Here's what we can do to resolve it.",
            ],
            "billing": [
                "I've pulled up your account. I can help you with this billing inquiry.",
                "Let me review your recent charges and see what's going on.",
            ],
        }
        return random.choice(responses.get(category, responses["general"]))

    def _generate_resolution(self, agent: dict, task_payload: dict) -> str:
        """Generate a resolution message."""
        return f"Issue resolved by {agent['name']}. Please let us know if you need anything else."

    def _can_resolve(self, agent: dict, task_payload: dict) -> bool:
        """Check if this agent can resolve the issue."""
        category = task_payload.get("category", "general")
        tier_needed = task_payload.get("tier_needed", 1)
        return agent["tier"] >= tier_needed

    def create_ticket(
        self,
        customer: str,
        category: str,
        description: str,
        priority: str = "medium",
    ) -> Ticket:
        """Create a new support ticket."""
        self.ticket_counter += 1
        ticket_id = f"TKT-{self.ticket_counter}"

        # Determine tier needed
        tier_map = {
            "general": 1,
            "technical": 2,
            "billing": 2,
            "escalation": 3,
        }

        ticket = Ticket(
            id=ticket_id,
            customer=customer,
            category=category,
            priority=priority,
            description=description,
            tier_needed=tier_map.get(category, 1),
        )

        self.tickets[ticket_id] = ticket
        self.metrics["total_tickets"] += 1

        return ticket

    async def handle_ticket(self, ticket: Ticket) -> dict:
        """Process a ticket through the support team."""
        print(f"\n📨 New Ticket: {ticket.id}")
        print(f"  Customer: {ticket.customer}")
        print(f"  Category: {ticket.category}")
        print(f"  Priority: {ticket.priority}")
        print(f"  Description: {ticket.description[:60]}...")

        # Find appropriate agent
        required_capabilities = [ticket.category]
        agent = self.coordinator._registry.find_best_agent(
            required_capabilities=required_capabilities,
        )

        if agent is None:
            print(f"  ⚠️ No agents available for category: {ticket.category}")
            return {"status": "failed", "reason": "No agents available"}

        # First response
        response_task = create_task(
            description=f"Respond to ticket {ticket.id}",
            capabilities=required_capabilities,
            payload={
                "ticket_id": ticket.id,
                "category": ticket.category,
                "tier_needed": ticket.tier_needed,
                "action": "respond",
            },
        )

        response_result = await self.coordinator.submit_task(response_task, wait_for_completion=True)

        if response_result and response_result.success:
            result_data = response_result.result
            print(f"  💬 {result_data.get('agent_name')}: {result_data.get('response', 'Responded')}")
            ticket.assigned_to = result_data.get("agent_id")
            ticket.status = "assigned"

            # Check if can resolve
            if result_data.get("can_resolve", False):
                resolve_task = create_task(
                    description=f"Resolve ticket {ticket.id}",
                    capabilities=required_capabilities,
                    payload={
                        "ticket_id": ticket.id,
                        "category": ticket.category,
                        "action": "resolve",
                    },
                )

                resolve_result = await self.coordinator.submit_task(resolve_task, wait_for_completion=True)

                if resolve_result and resolve_result.success:
                    ticket.status = "resolved"
                    ticket.resolution = resolve_result.result.get("resolution")
                    self.metrics["resolved"] += 1
                    print(f"  ✅ {ticket.resolution}")
                else:
                    # Escalate
                    ticket.tier_needed = min(ticket.tier_needed + 1, 3)
                    await self._escalate_ticket(ticket)
            else:
                # Escalate to higher tier
                await self._escalate_ticket(ticket)

            return {"status": ticket.status, "ticket_id": ticket.id}

        return {"status": "failed", "reason": "Response failed"}

    async def _escalate_ticket(self, ticket: Ticket) -> None:
        """Escalate a ticket to the next tier."""
        print(f"  ⬆️ Escalating {ticket.id} to Tier {ticket.tier_needed}")
        ticket.status = "escalated"
        self.metrics["escalated"] += 1

        if ticket.tier_needed > 2:
            print(f"  ℹ️ Ticket {ticket.id} escalated to Tier 3 (Management)")
            return

    async def simulate_day(self, num_tickets: int = 10) -> dict:
        """Simulate a day of customer support."""
        print(f"\n{'='*50}")
        print(f"Simulating {num_tickets} incoming tickets...")
        print(f"{'='*50}")

        customers = ["Acme Corp", "Globex Inc", "Soylent Corp", "Initech", "Umbrella Corp"]
        categories = ["general", "technical", "billing", "general", "technical"]
        descriptions = [
            "I can't log into my account",
            "The system is down",
            "I was charged twice",
            "Where do I find my invoices?",
            "My data isn't syncing",
        ]
        priorities = ["low", "medium", "high", "medium", "urgent"]

        for i in range(num_tickets):
            ticket = self.create_ticket(
                customer=random.choice(customers),
                category=random.choice(categories),
                description=random.choice(descriptions),
                priority=random.choice(priorities),
            )

            await self.handle_ticket(ticket)
            await asyncio.sleep(0.1)  # Small delay between tickets

        # Summary
        print(f"\n{'='*50}")
        print("End of Day Summary")
        print(f"{'='*50}")
        print(f"  Total Tickets: {self.metrics['total_tickets']}")
        print(f"  Resolved: {self.metrics['resolved']}")
        print(f"  Escalated: {self.metrics['escalated']}")

        return self.metrics

    async def cleanup(self) -> None:
        """Clean up after the scenario."""
        if self.coordinator:
            await self.coordinator.shutdown()


async def main():
    """Run the customer service scenario."""
    team = CustomerServiceTeam()

    try:
        await team.setup()
        await team.simulate_day(num_tickets=15)

    finally:
        await team.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
