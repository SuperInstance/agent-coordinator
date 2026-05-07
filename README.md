# agent-coordinator

Multi-agent coordination framework with task distribution, inter-agent messaging, and health monitoring.

## Concept

A central coordinator manages agent registration, task assignment, message passing, and health tracking. Agents operate asynchronously while the coordinator ensures work flows smoothly.

## Features

- **Agent Registration** — Register agents with unique IDs and track their state (idle, working, blocked, offline)
- **Task Distribution** — Submit tasks with priority levels, assign to specific agents
- **Inter-Agent Messaging** — Agents communicate through the coordinator's message log
- **Health Monitoring** — Per-agent health snapshots with state, completed task count, and health score

## Usage

```bash
python src/coordinator.py
```

Output demonstrates:
- 3 agents registering
- Task submission with priorities
- Task assignment to agents
- Inter-agent messaging
- Health check reporting

## Architecture

```
Coordinator
├── agents{} — registered agent roster
├── tasks{} — task queue with priority
├── message_log[] — inter-agent communications
└── health_check() — agent status snapshots
```

### Core Classes

**Agent** — Represents a crew member with `id`, `name`, `state`, `tasks_completed`, and `health_score`

**Task** — A unit of work with `id`, `description`, `priority`, `assigned_to`, and `status`

**Coordinator** — Central hub exposing:
- `register(name)` → registers an agent, returns agent ID
- `submit_task(description, priority)` → submits a task, returns task ID
- `assign_task(task_id, agent_id)` → assigns a task to an agent
- `send_message(from_id, to_id, message)` → logs an inter-agent message
- `health_check(agent_id)` → returns health snapshot for an agent

## Related Repos

- [fleet-agent](https://github.com/SuperInstance/fleet-agent) — Agent runtime and execution
- [agent-bootcamp](https://github.com/SuperInstance/agent-bootcamp) — Agent training and onboarding
- [agent-forge](https://github.com/SuperInstance/agent-forge) — Agent creation and configuration

## License

MIT
