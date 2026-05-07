# agent-coordinator

Multi-agent coordination framework with task distribution, inter-agent messaging, and health monitoring.

## Concept

A central coordinator manages agent registration, task assignment, message passing, and health tracking. Agents operate asynchronously while the coordinator ensures work flows smoothly.

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