"""
Agent Coordinator - Main coordinator class for managing agents.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field

from agent_coordinator.agent import Agent, AgentState, AgentRole, AgentConfig, create_agent, TaskAgent
from agent_coordinator.task import Task, TaskStatus, TaskResult, TaskBuilder
from agent_coordinator.message import AgentMessage, MessageType
from agent_coordinator.registry import AgentRegistry
from agent_coordinator.task_queue import TaskQueue, LoadBalancingStrategy
from agent_coordinator.message_bus import MessageBus
from agent_coordinator.monitor import NetworkMonitor, HealthStatus
from agent_coordinator.metrics import MetricsCollector
from agent_coordinator.events import EventBus, EventType, Event

logger = logging.getLogger(__name__)


@dataclass
class CoordinatorConfig:
    """Configuration for the AgentCoordinator."""
    name: str = "coordinator"
    heartbeat_timeout: float = 60.0
    health_check_interval: float = 30.0
    task_processing_interval: float = 0.1
    max_retries: int = 3
    retry_delay: float = 1.0
    auto_recovery: bool = True
    load_balancing: str = LoadBalancingStrategy.LEAST_LOADED


class AgentCoordinator:
    """
    Main coordinator for managing teams of AI agents.

    The coordinator provides:
    - Agent lifecycle management (spawn, monitor, terminate)
    - Task distribution and scheduling
    - Inter-agent communication
    - Health monitoring
    - Metrics collection
    - Event notifications

    Example:
        coordinator = AgentCoordinator(name="mission-control")

        # Register a role
        role = AgentRole(name="worker", capabilities=["process"])
        await coordinator.register_role(role)

        # Spawn an agent
        agent = await coordinator.spawn_agent("worker-1", role="worker")

        # Submit a task
        task = Task(description="Process data", required_capabilities=["process"])
        result = await coordinator.submit_task(task)

        # Shutdown
        await coordinator.shutdown()
    """

    def __init__(self, config: CoordinatorConfig = None):
        self.config = config or CoordinatorConfig()

        # Core components
        self._registry = AgentRegistry()
        self._task_queue = TaskQueue(load_balancing=self.config.load_balancing)
        self._message_bus = MessageBus()
        self._monitor = NetworkMonitor(
            heartbeat_timeout=self.config.heartbeat_timeout,
            health_check_interval=self.config.health_check_interval,
        )
        self._metrics = MetricsCollector()
        self._event_bus = EventBus()

        # State
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None

        # Task completion tracking
        self._task_completions: Dict[str, asyncio.Future[TaskResult]] = {}

        # Setup callbacks
        self._setup_callbacks()

        logger.info(f"AgentCoordinator '{self.config.name}' created")

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def task_queue(self) -> TaskQueue:
        return self._task_queue

    @property
    def message_bus(self) -> MessageBus:
        return self._message_bus

    @property
    def monitor(self) -> NetworkMonitor:
        return self._monitor

    @property
    def metrics(self) -> MetricsCollector:
        return self._metrics

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    async def start(self) -> None:
        """Start the coordinator and all subsystems."""
        if self._running:
            logger.warning(f"Coordinator '{self.name}' is already running")
            return

        self._running = True

        # Start subsystems
        await self._message_bus.start()
        await self._monitor.start()

        # Start task processing loop
        self._processing_task = asyncio.create_task(self._processing_loop())

        # Emit event
        await self._emit_event(EventType.SYSTEM_STARTED, {"coordinator": self.name})

        logger.info(f"AgentCoordinator '{self.name}' started")

    async def shutdown(self) -> None:
        """Shutdown the coordinator and all agents."""
        if not self._running:
            return

        self._running = False

        # Emit event
        await self._emit_event(EventType.SYSTEM_STOPPING, {"coordinator": self.name})

        # Stop processing loop
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        # Stop all agents
        agents = list(self._registry._agents.values())
        for agent in agents:
            await agent.stop()

        # Stop subsystems
        await self._message_bus.stop()
        await self._monitor.stop()

        # Clear registries
        self._registry._agents.clear()
        self._registry._agent_info.clear()

        # Emit event
        await self._emit_event(EventType.SYSTEM_STOPPED, {"coordinator": self.name})

        logger.info(f"AgentCoordinator '{self.name}' shut down")

    # Role management

    async def register_role(self, role: AgentRole) -> None:
        """Register an agent role."""
        await self._registry.register_role(role)
        await self._emit_event(
            EventType.AGENT_REGISTERED,
            {"role": role.name, "capabilities": role.capabilities},
        )

    # Agent management

    async def spawn_agent(
        self,
        agent_id: str,
        role: str,
        task_handler: Optional[Callable[[Task], Any]] = None,
        message_handler: Optional[Callable[[AgentMessage], None]] = None,
        auto_start: bool = True,
        **config_kwargs,
    ) -> Agent:
        """
        Spawn a new agent.

        Args:
            agent_id: Unique ID for the agent
            role: Role name for the agent
            task_handler: Optional handler for task processing
            message_handler: Optional handler for messages
            auto_start: Start the agent immediately
            **config_kwargs: Additional configuration

        Returns:
            The created agent
        """
        agent_role = self._registry.get_role(role)
        if agent_role is None:
            raise ValueError(f"Role '{role}' not registered")

        # Create agent config
        config = AgentConfig(
            agent_id=agent_id,
            role=role,
            **config_kwargs,
        )

        # Create agent
        if task_handler:
            agent = TaskAgent(config, agent_role, task_handler, message_handler)
        else:
            agent = Agent(config, agent_role, message_handler)

        # Set up callbacks
        agent.add_task_complete_callback(self._on_task_complete)

        # Register with subsystems
        await self._registry.register(agent)
        self._message_bus.register_agent(agent)
        self._monitor.register_agent(agent_id)
        self._metrics.register_agent(agent_id)

        # Start agent if requested
        if auto_start:
            await agent.start()
            await self._emit_event(EventType.AGENT_STARTED, {"agent_id": agent_id})

        logger.info(f"Spawned agent '{agent_id}' with role '{role}'")

        return agent

    async def terminate_agent(self, agent_id: str) -> bool:
        """Terminate an agent."""
        agent = self._registry.get(agent_id)
        if agent is None:
            logger.warning(f"Agent '{agent_id}' not found")
            return False

        await agent.stop()

        # Unregister from subsystems
        await self._registry.unregister(agent_id)
        self._message_bus.unregister_agent(agent_id)
        self._monitor.unregister_agent(agent_id)

        await self._emit_event(EventType.AGENT_STOPPED, {"agent_id": agent_id})

        logger.info(f"Terminated agent '{agent_id}'")
        return True

    # Task management

    async def submit_task(self, task: Task, wait_for_completion: bool = False) -> Optional[TaskResult]:
        """
        Submit a task for execution.

        Args:
            task: The task to execute
            wait_for_completion: Wait for task to complete

        Returns:
            Task result if wait_for_completion is True, None otherwise
        """
        if not self._running:
            raise RuntimeError("Coordinator is not running")

        # Create future for completion tracking
        if wait_for_completion:
            self._task_completions[task.id] = asyncio.Future()

        await self._task_queue.enqueue(task)

        await self._emit_event(
            EventType.TASK_QUEUED,
            {"task_id": task.id, "description": task.description},
        )

        if wait_for_completion:
            try:
                result = await self._task_completions[task.id]
                return result
            finally:
                self._task_completions.pop(task.id, None)

        return None

    async def submit_tasks(
        self,
        tasks: List[Task],
        wait_for_all: bool = False,
    ) -> List[Optional[TaskResult]]:
        """
        Submit multiple tasks.

        Args:
            tasks: List of tasks to execute
            wait_for_all: Wait for all tasks to complete

        Returns:
            List of results if wait_for_all is True
        """
        if not wait_for_all:
            for task in tasks:
                await self._task_queue.enqueue(task)
            return [None] * len(tasks)

        # Submit all and wait
        futures = []
        for task in tasks:
            self._task_completions[task.id] = asyncio.Future()
            await self._task_queue.enqueue(task)

        # Wait for all completions
        results = []
        for task in tasks:
            try:
                result = await self._task_completions[task.id]
                results.append(result)
            finally:
                self._task_completions.pop(task.id, None)

        return results

    # Query methods

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._registry.get(agent_id)

    def get_agents_by_role(self, role: str) -> List[Agent]:
        """Get all agents with a specific role."""
        return self._registry.get_by_role(role)

    def get_available_agents(self) -> List[Agent]:
        """Get all available agents."""
        return self._registry.get_available()

    async def get_status(self) -> Dict[str, Any]:
        """Get coordinator status."""
        return {
            "name": self.name,
            "running": self._running,
            "agents": self._registry.get_status_summary(),
            "tasks": self._task_queue.get_statistics(),
            "health": self._monitor.get_system_health().__dict__,
            "metrics": self._metrics.get_system_metrics().__dict__,
            "message_bus": self._message_bus.get_statistics(),
        }

    async def get_agent_metrics(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific agent."""
        metrics = self._metrics.get_agent_metrics(agent_id)
        return metrics.to_dict() if metrics else None

    async def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get task history."""
        results = self._task_queue.get_history(limit)
        return [r.to_dict() for r in results]

    # Event streaming

    async def event_stream(self):
        """Stream events from the coordinator."""
        queue: asyncio.Queue[Event] = asyncio.Queue()

        async def handler(event: Event):
            await queue.put(event)

        self._event_bus.subscribe([EventType("*")], handler)

        try:
            while self._running:
                yield await queue.get()
        finally:
            self._event_bus.unsubscribe_all(handler)

    # Configuration

    def set_load_balancing_strategy(self, strategy: str) -> None:
        """Set the load balancing strategy."""
        self._task_queue.set_load_balancing(strategy)

    def enable_auto_recovery(self) -> None:
        """Enable automatic agent recovery."""
        self.config.auto_recovery = True

    def disable_auto_recovery(self) -> None:
        """Disable automatic agent recovery."""
        self.config.auto_recovery = False

    # Internal methods

    def _setup_callbacks(self) -> None:
        """Set up callbacks between subsystems."""

        # Monitor heartbeats from agents
        async def on_agent_registered(agent: Agent):
            self._monitor.register_agent(agent.id)
            await self._emit_event(
                EventType.AGENT_REGISTERED,
                {"agent_id": agent.id, "role": agent.role.name},
            )

        self._registry.add_registration_callback(on_agent_registered)

        # Monitor state changes
        async def on_state_change(agent_id: str, state: AgentState):
            self._monitor.record_state_change(agent_id, state)
            await self._emit_event(
                EventType.AGENT_STATE_CHANGED,
                {"agent_id": agent_id, "state": state.value},
            )

        self._registry.add_state_change_callback(on_state_change)

        # Monitor agent failures
        def on_agent_failure(agent_id: str, error: str):
            self._monitor.record_failure(agent_id, error)
            asyncio.create_task(
                self._emit_event(EventType.FAILURE_DETECTED, {"agent_id": agent_id, "error": error})
            )

        self._monitor.add_failure_callback(on_agent_failure)

        # Auto-recovery
        if self.config.auto_recovery:
            self._monitor.add_offline_callback(self._on_agent_offline)

    async def _processing_loop(self) -> None:
        """Main processing loop for task distribution."""
        try:
            while self._running:
                await self._task_queue.process_queue(
                    get_available_agents=self.get_available_agents,
                    get_agent=self._registry.get,
                )
                await asyncio.sleep(self.config.task_processing_interval)

        except asyncio.CancelledError:
            logger.debug("Processing loop cancelled")
        except Exception as e:
            logger.error(f"Processing loop error: {e}")
            await self._emit_event(EventType.SYSTEM_ERROR, {"error": str(e)})

    def _on_task_complete(self, result: TaskResult) -> None:
        """Handle task completion."""
        self._task_queue.mark_complete(result)

        # Record metrics
        self._metrics.record_task_complete(
            result.agent_id,
            result.execution_time or 0,
            result.success,
        )

        # Notify waiting futures
        future = self._task_completions.get(result.task_id)
        if future and not future.done():
            future.set_result(result)

        # Emit event
        event_type = EventType.TASK_COMPLETED if result.success else EventType.TASK_FAILED
        asyncio.create_task(
            self._emit_event(
                event_type,
                {"task_id": result.task_id, "agent_id": result.agent_id, "success": result.success},
            )
        )

    async def _on_agent_offline(self, agent_id: str) -> None:
        """Handle agent going offline."""
        if not self.config.auto_recovery:
            return

        logger.warning(f"Agent {agent_id} went offline, auto-recovery enabled")

        # In a real implementation, this would restart the agent
        # For now, just log the event
        await self._emit_event(EventType.AGENT_OFFLINE, {"agent_id": agent_id})

    async def _emit_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Emit an event to the event bus."""
        event = Event(type=event_type, data=data, source=self.name)
        await self._event_bus.emit(event)


# Convenience functions

def create_coordinator(
    name: str = "coordinator",
    **config_kwargs,
) -> AgentCoordinator:
    """Create a new coordinator with the given configuration."""
    config = CoordinatorConfig(name=name, **config_kwargs)
    return AgentCoordinator(config)


async def run_coordinator(
    name: str = "coordinator",
    **config_kwargs,
) -> AgentCoordinator:
    """Create and start a coordinator."""
    coordinator = create_coordinator(name, **config_kwargs)
    await coordinator.start()
    return coordinator
