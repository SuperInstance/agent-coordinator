# Agent Coordinator


## Meta

**Domain:** ai-agents
**Depends on:** —
**Depended by:** —
**Implements:** Multi-agent coordination framework for managing teams of AI agents with task dis...
**Related:** —


**Mission control for a fleet of AI agents. Assign, route, monitor, recover.**

Multiple agents need to work together without stepping on each other. The Agent Coordinator manages their lifecycles — who's doing what, what they've learned, what's waiting, what failed and needs retry.

This is the Python framework that runs the [Cocapn fleet](https://github.com/SuperInstance). Every agent has a role, every task has a queue, every message has a route.

---

## What It Does

**Organize agents into packs.** Each pack has a role and a set of capabilities. Agents come and go as the workload shifts.

**Distribute tasks.** The coordinator knows which agents are available, which are busy, and which have the right skills. Work goes where it fits.

**Route messages.** Agents don't talk to each other directly. They talk through the message bus. Topic-based routing, with subscriptions and acknowledgments.

**Monitor health.** Every agent reports heartbeat, load, and completion status. The coordinator detects silence, re-queues lost work, and scales idle agents down.

**Handle failures.** If an agent goes silent mid-task, the coordinator re-queues within the heartbeat timeout. No task is lost, no work is duplicated (at-most-once within the timeout window).

---

## Architecture

```
AgentCoordinator
├── AgentRegistry     — Every agent, its capabilities, its status
├── TaskQueue         — Priority queue, bounded, with dead-letter
├── MessageBus        — Topic-based pub/sub, at-least-once delivery
├── NetworkMonitor    — Heartbeat, health, connectivity scoring
└── MetricsCollector  — Throughput, latency, error rates
```

## Quick Start

```python
from agent_coordinator import AgentCoordinator, Agent, Task

coord = AgentCoordinator()

# Register a worker
coord.register(Agent(
    id="forge-1",
    capabilities=["rust", "cuda", "proofs"],
    max_concurrent=3
))

# Submit a task
task_id = coord.submit(Task(
    type="compile",
    payload={"crate": "eisenstein", "target": "aarch64"},
    priority=2
))

# Route a message — topic-based
coord.publish("fleet/compilation/complete", {
    "agent": "forge-1",
    "status": "ok",
    "artifacts": ["eisenstein.aarch64"]
})

# Check health
status = coord.health()
# → {"forge-1": {"load": 2, "heartbeat_ok": True, "tasks_completed": 47}}
```

## Installation

```bash
pip install agent-coordinator
```

---

## How It Fits

The Agent Coordinator is the mission control layer of the [SuperInstance](https://github.com/SuperInstance/superinstance) fleet:

- **[cocapn](https://github.com/SuperInstance/cocapn)** — the helm, fleet-wide coordination
- **[agent-coordinator](https://github.com/SuperInstance/agent-coordinator)** — this, the runtime task management
- **[baton-skill](https://github.com/SuperInstance/baton-skill)** — generational handoff between agents
- **[arena-combat-analyst-1](https://github.com/SuperInstance/arena-combat-analyst-1)** — self-play skill acquisition
- **[casting-call](https://github.com/SuperInstance/casting-call)** — which model plays which role

---

## License

MIT
