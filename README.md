# Agent Coordinator

> **Mission Control for Managing Teams of AI Agents**

A comprehensive Python framework for coordinating multi-agent systems. Inspired by the "Pack Dashboard" concept from LucidDreamer UI, this system provides complete control over agent lifecycles, communication, task distribution, and monitoring.

## Overview

Agent Coordinator enables you to:

- **Manage Agent Packs**: Organize agents into teams (packs) with specialized roles
- **Coordinate Tasks**: Distribute work across agents with intelligent load balancing
- **Route Messages**: Facilitate communication between agents
- **Monitor Health**: Track agent status, performance metrics, and system health
- **Visualize Networks**: See agent relationships and communication patterns
- **Handle Failures**: Automatic fault tolerance and recovery

## Architecture

```
AgentCoordinator
├── AgentRegistry    - Track all agents and their capabilities
├── TaskQueue        - Distribute work to available agents
├── MessageBus       - Inter-agent communication fabric
├── NetworkMonitor   - Track agent health and connectivity
└── MetricsCollector - Performance data and analytics
```

## Installation

```bash
# Basic installation
pip install agent-coordinator

# With visualization support
pip install agent-coordinator[viz]

# Development installation
git clone https://github.com/casey/websocket-fabric.git
cd websocket-fabric/agent-coordinator
pip install -e ".[dev,viz]"
```

## Quick Start

```python
import asyncio
from agent_coordinator import AgentCoordinator, Agent, AgentRole, Task

async def main():
    # Create a coordinator
    coordinator = AgentCoordinator(name="mission-control")

    # Define agent roles
    roles = [
        AgentRole(name="leader", capabilities=["planning", "coordination"]),
        AgentRole(name="worker", capabilities=["execution", "processing"]),
        AgentRole(name="analyst", capabilities=["analysis", "reporting"]),
    ]

    # Register roles
    for role in roles:
        await coordinator.register_role(role)

    # Spawn agents
    leader = await coordinator.spawn_agent("alpha", role="leader")
    workers = [await coordinator.spawn_agent(f"worker-{i}", role="worker") for i in range(3)]
    analyst = await coordinator.spawn_agent("beta", role="analyst")

    # Submit a task
    task = Task(
        id="task-1",
        description="Analyze data and generate report",
        required_capabilities=["processing", "analysis"],
        payload={"data": [1, 2, 3, 4, 5]}
    )

    result = await coordinator.submit_task(task)
    print(f"Task result: {result}")

    # Clean up
    await coordinator.shutdown()

asyncio.run(main())
```

## Example Scenarios

### D&D Party Coordination

```python
from agent_coordinator import AgentCoordinator, AgentRole
from examples.dnd_party import DNDPartyScenarios

# Create a classic D&D adventuring party
coordinator = AgentCoordinator(name="adventuring-party")

roles = [
    AgentRole(name="fighter", capabilities=["tank", "melee"], emoji="⚔️"),
    AgentRole(name="cleric", capabilities=["heal", "support"], emoji="🙏"),
    AgentRole(name="wizard", capabilities=["magic", "aoe"], emoji="🔮"),
    AgentRole(name="rogue", capabilities=["stealth", "scout"], emoji="🗡️"),
]

# Spawn the party
party = await DNDPartyScenarios.create_party(coordinator)

# Encounter!
await party.handle_encounter(goblins=5, boss=True)
```

### Customer Service Team

```python
from examples.customer_service import CustomerServiceTeam

# Create a tiered support team
team = CustomerServiceTeam()

# Tier 1: Basic support
await team.add_agent("tier1-1", tier=1, specialties=["general", "password-reset"])

# Tier 2: Technical support
await team.add_agent("tier2-1", tier=2, specialties=["technical", "billing"])

# Tier 3: Escalations
await team.add_agent("tier3-1", tier=3, specialties=["escalation", "management"])

# Handle incoming tickets
await team.handle_ticket(ticket_id=12345, category="billing", priority="high")
```

### Research Collaboration

```python
from examples.research_team import ResearchCollaboration

# Create a multi-disciplinary research team
research = ResearchCollaboration()

# Add specialized researchers
await research.add_researcher("data-scientist", field="ml")
await research.add_researcher("domain-expert", field="biology")
await research.add_researcher("analyst", field="statistics")

# Run a study
results = await research.run_study(
    hypothesis="Gene X affects protein Y",
    methodology="experimental"
)
```

## Core Concepts

### Agents

Agents are the fundamental units of work. Each agent has:

- **ID**: Unique identifier
- **Role**: Defines capabilities and behaviors
- **State**: Current status (idle, busy, offline, etc.)
- **Capabilities**: What the agent can do
- **Metrics**: Performance tracking data

### Roles

Roles define agent capabilities and behaviors:

```python
role = AgentRole(
    name="data-processor",
    capabilities=["parse", "transform", "validate"],
    max_concurrent_tasks=3,
    priority=10
)
```

### Tasks

Tasks represent units of work:

```python
task = Task(
    id="unique-id",
    description="Process dataset",
    required_capabilities=["parse", "transform"],
    payload={"dataset": "data.csv"},
    timeout=300,
    priority=5
)
```

### Messages

Agents communicate via messages:

```python
message = AgentMessage(
    from_agent="agent-1",
    to_agent="agent-2",
    message_type="request",
    content={"action": "help"},
    correlation_id="msg-123"
)
```

## Advanced Features

### Fault Tolerance

```python
coordinator = AgentCoordinator(
    name="resilient-system",
    max_retries=3,
    retry_delay=1.0,
    heartbeat_interval=30
)

# Auto-recovery on agent failure
await coordinator.enable_auto_recovery()
```

### Load Balancing

```python
# Strategies: round_robin, least_loaded, capability_match, random
coordinator.set_load_balancing_strategy("least_loaded")
```

### Monitoring

```python
# Get system status
status = await coordinator.get_status()

# Get agent metrics
metrics = await coordinator.get_agent_metrics("agent-1")

# Get task history
history = await coordinator.get_task_history(limit=100)
```

### Event Streaming

```python
async for event in coordinator.event_stream():
    print(f"Event: {event.type} - {event.data}")
```

## API Reference

### AgentCoordinator

Main coordinator class for managing agents.

#### Methods

- `register_role(role: AgentRole)` - Register a new agent role
- `spawn_agent(agent_id: str, role: str, **kwargs)` - Create a new agent
- `terminate_agent(agent_id: str)` - Shut down an agent
- `submit_task(task: Task)` - Submit work to be executed
- `get_agent(agent_id: str)` - Get agent by ID
- `get_agents_by_role(role: str)` - Get all agents with a role
- `get_status()` - Get system status
- `shutdown()` - Gracefully shutdown coordinator

### Agent

Represents a single agent.

#### Properties

- `id` - Unique identifier
- `role` - Agent role
- `state` - Current state
- `capabilities` - List of capabilities
- `metrics` - Performance metrics

#### Methods

- `execute(task: Task)` - Execute a task
- `send_message(message: AgentMessage)` - Send a message
- `get_status()` - Get agent status

## Visualization

Enable visualization to see agent networks:

```python
from agent_coordinator.visualization import NetworkVisualizer

visualizer = NetworkVisualizer(coordinator)

# Generate network graph
visualizer.render_network(output="network.png")

# Show metrics dashboard
visualizer.show_dashboard()
```

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=agent_coordinator --cov-report=html

# Run specific example scenarios
pytest tests/test_scenarios.py::test_dnd_party
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.
