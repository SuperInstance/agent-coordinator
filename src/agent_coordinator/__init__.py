"""
Agent Coordinator - Multi-Agent Coordination Framework

A comprehensive system for managing teams of AI agents with:
- Agent lifecycle management
- Inter-agent communication
- Task orchestration
- Load balancing
- Fault tolerance
- Metrics and monitoring
"""

__version__ = "0.1.0"
__author__ = "Casey"

from agent_coordinator.coordinator import AgentCoordinator, CoordinatorConfig, create_coordinator, run_coordinator
from agent_coordinator.agent import Agent, AgentState, AgentRole, AgentConfig, create_agent, TaskAgent
from agent_coordinator.task import Task, TaskStatus, TaskResult, TaskBuilder, TaskPriority, create_task
from agent_coordinator.message import AgentMessage, MessageType, MessagePriority, create_message, broadcast_message
from agent_coordinator.registry import AgentRegistry
from agent_coordinator.task_queue import TaskQueue, PrioritizedTask, LoadBalancingStrategy
from agent_coordinator.message_bus import MessageBus
from agent_coordinator.monitor import NetworkMonitor, HealthStatus
from agent_coordinator.metrics import MetricsCollector, AgentMetrics
from agent_coordinator.events import Event, EventType, EventBus, get_event_bus, emit_event
from agent_coordinator.visualization import NetworkVisualizer, ConsoleDashboard, create_visualizer, create_console_dashboard

__all__ = [
    # Core
    "AgentCoordinator",
    "CoordinatorConfig",
    "create_coordinator",
    "run_coordinator",
    # Agent
    "Agent",
    "AgentState",
    "AgentRole",
    "AgentConfig",
    "create_agent",
    "TaskAgent",
    # Task
    "Task",
    "TaskStatus",
    "TaskResult",
    "TaskBuilder",
    "TaskPriority",
    "create_task",
    # Message
    "AgentMessage",
    "MessageType",
    "MessagePriority",
    "create_message",
    "broadcast_message",
    # Infrastructure
    "AgentRegistry",
    "TaskQueue",
    "PrioritizedTask",
    "LoadBalancingStrategy",
    "MessageBus",
    "NetworkMonitor",
    "HealthStatus",
    "MetricsCollector",
    "AgentMetrics",
    # Events
    "Event",
    "EventType",
    "EventBus",
    "get_event_bus",
    "emit_event",
    # Visualization
    "NetworkVisualizer",
    "ConsoleDashboard",
    "create_visualizer",
    "create_console_dashboard",
]
