"""
Agent module - Defines Agent, AgentState, and AgentRole classes.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging

from agent_coordinator.task import Task, TaskResult
from agent_coordinator.message import AgentMessage
from agent_coordinator.metrics import AgentMetrics

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """Possible states for an agent."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    SUSPENDED = "suspended"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class AgentRole:
    """Defines the role and capabilities of an agent."""
    name: str
    capabilities: List[str] = field(default_factory=list)
    max_concurrent_tasks: int = 1
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    emoji: str = ""

    def can_handle(self, required_capabilities: List[str]) -> bool:
        """Check if this role has the required capabilities."""
        if not required_capabilities:
            return True
        return all(cap in self.capabilities for cap in required_capabilities)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other) -> bool:
        if not isinstance(other, AgentRole):
            return False
        return self.name == other.name


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    agent_id: str
    role: str
    heartbeat_interval: float = 30.0
    task_timeout: float = 300.0
    max_retries: int = 3
    retry_delay: float = 1.0
    auto_restart: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class Agent:
    """
    Represents a single agent in the coordinator system.

    Agents are autonomous workers that can:
    - Receive and execute tasks
    - Communicate with other agents
    - Report their status and metrics
    - Handle failures with retries
    """

    def __init__(
        self,
        config: AgentConfig,
        role: AgentRole,
        message_handler: Optional[Callable[[AgentMessage], None]] = None,
    ):
        self.config = config
        self.role = role
        self._state = AgentState.INITIALIZING
        self._message_handler = message_handler

        # Task management
        self._current_tasks: Dict[str, Task] = {}
        self._task_queue: asyncio.Queue[Task] = asyncio.Queue()
        self._task_results: Dict[str, TaskResult] = {}

        # Metrics
        self._metrics = AgentMetrics(agent_id=config.agent_id)
        self._created_at = datetime.now()

        # Communication
        self._message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()

        # Worker task
        self._worker_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Event callbacks
        self._on_state_change: List[Callable[[AgentState], None]] = []
        self._on_task_complete: List[Callable[[TaskResult], None]] = []

        logger.info(f"Agent {config.agent_id} created with role {role.name}")

    @property
    def id(self) -> str:
        return self.config.agent_id

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def capabilities(self) -> List[str]:
        return self.role.capabilities

    @property
    def metrics(self) -> AgentMetrics:
        return self._metrics

    @property
    def current_task_count(self) -> int:
        return len(self._current_tasks)

    @property
    def is_available(self) -> bool:
        """Check if agent is available for new tasks."""
        return (
            self._state == AgentState.IDLE and
            len(self._current_tasks) < self.role.max_concurrent_tasks
        )

    @property
    def uptime(self) -> float:
        """Get agent uptime in seconds."""
        return (datetime.now() - self._created_at).total_seconds()

    def add_state_change_callback(self, callback: Callable[[AgentState], None]) -> None:
        """Add a callback for state changes."""
        self._on_state_change.append(callback)

    def add_task_complete_callback(self, callback: Callable[[TaskResult], None]) -> None:
        """Add a callback for task completion."""
        self._on_task_complete.append(callback)

    async def start(self) -> None:
        """Start the agent's worker loop."""
        if self._worker_task is not None:
            logger.warning(f"Agent {self.id} is already running")
            return

        self._set_state(AgentState.IDLE)
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(f"Agent {self.id} started")

    async def stop(self) -> None:
        """Stop the agent."""
        self._set_state(AgentState.TERMINATED)

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info(f"Agent {self.id} stopped")

    async def submit_task(self, task: Task) -> None:
        """Submit a task to this agent."""
        if self._state == AgentState.TERMINATED:
            raise RuntimeError(f"Agent {self.id} is terminated")

        await self._task_queue.put(task)
        logger.debug(f"Task {task.id} queued for agent {self.id}")

    async def send_message(self, message: AgentMessage) -> None:
        """Send a message to this agent."""
        await self._message_queue.put(message)

    def get_status(self) -> Dict[str, Any]:
        """Get the agent's current status."""
        return {
            "id": self.id,
            "role": self.role.name,
            "state": self._state.value,
            "capabilities": self.capabilities,
            "current_tasks": list(self._current_tasks.keys()),
            "uptime_seconds": self.uptime,
            "metrics": self._metrics.to_dict(),
        }

    async def _worker_loop(self) -> None:
        """Main worker loop for processing tasks and messages."""
        try:
            while self._state != AgentState.TERMINATED:
                # Wait for either a task or a message
                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(self._task_queue.get()),
                        asyncio.create_task(self._message_queue.get()),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()

                # Process completed item
                for item in done:
                    try:
                        result = item.result()
                        if isinstance(result, Task):
                            await self._execute_task(result)
                        elif isinstance(result, AgentMessage):
                            await self._handle_message(result)
                    except Exception as e:
                        logger.error(f"Error in worker loop: {e}")

        except asyncio.CancelledError:
            logger.debug(f"Agent {self.id} worker loop cancelled")
        except Exception as e:
            logger.error(f"Agent {self.id} worker loop error: {e}")
            self._set_state(AgentState.FAILED)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat signals."""
        try:
            while self._state != AgentState.TERMINATED:
                await asyncio.sleep(self.config.heartbeat_interval)

                if self._state != AgentState.TERMINATED:
                    self._metrics.record_heartbeat()
                    logger.debug(f"Heartbeat from agent {self.id}")

        except asyncio.CancelledError:
            logger.debug(f"Agent {self.id} heartbeat loop cancelled")

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task."""
        self._set_state(AgentState.BUSY)
        self._current_tasks[task.id] = task
        self._metrics.task_started()

        start_time = datetime.now()

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._process_task(task),
                timeout=self.config.task_timeout,
            )

            # Record success
            duration = (datetime.now() - start_time).total_seconds()
            self._metrics.task_completed(duration, success=True)

            # Store result
            self._task_results[task.id] = result

            # Notify callbacks
            for callback in self._on_task_complete:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Task complete callback error: {e}")

            logger.info(f"Agent {self.id} completed task {task.id}")

        except asyncio.TimeoutError:
            duration = (datetime.now() - start_time).total_seconds()
            self._metrics.task_completed(duration, success=False)

            result = TaskResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error="Task timeout",
            )
            self._task_results[task.id] = result

            logger.warning(f"Agent {self.id} timed out on task {task.id}")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self._metrics.task_completed(duration, success=False)

            result = TaskResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error=str(e),
            )
            self._task_results[task.id] = result

            logger.error(f"Agent {self.id} failed task {task.id}: {e}")

        finally:
            self._current_tasks.pop(task.id, None)
            if len(self._current_tasks) < self.role.max_concurrent_tasks:
                self._set_state(AgentState.IDLE)

    async def _process_task(self, task: Task) -> TaskResult:
        """
        Process a task. Override this method in subclasses.

        Base implementation just returns a success with the payload echoed.
        """
        # Simulate some work
        await asyncio.sleep(0.1)

        return TaskResult(
            task_id=task.id,
            agent_id=self.id,
            success=True,
            result=task.payload,
        )

    async def _handle_message(self, message: AgentMessage) -> None:
        """Handle an incoming message."""
        logger.debug(f"Agent {self.id} received message: {message.message_type}")

        if self._message_handler:
            try:
                if asyncio.iscoroutinefunction(self._message_handler):
                    await self._message_handler(message)
                else:
                    self._message_handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")

    def _set_state(self, state: AgentState) -> None:
        """Set the agent's state and notify callbacks."""
        old_state = self._state
        self._state = state

        for callback in self._on_state_change:
            try:
                callback(state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

        logger.debug(f"Agent {self.id} state: {old_state.value} -> {state.value}")


class TaskAgent(Agent):
    """An Agent that executes actual tasks via a handler function."""

    def __init__(
        self,
        config: AgentConfig,
        role: AgentRole,
        task_handler: Callable[[Task], Any],
        message_handler: Optional[Callable[[AgentMessage], None]] = None,
    ):
        super().__init__(config, role, message_handler)
        self._task_handler = task_handler

    async def _process_task(self, task: Task) -> TaskResult:
        """Process task using the provided handler."""
        try:
            result = self._task_handler(task)

            # If the handler returned a coroutine, await it
            if asyncio.iscoroutine(result):
                result = await result

            return TaskResult(
                task_id=task.id,
                agent_id=self.id,
                success=True,
                result=result,
            )

        except Exception as e:
            return TaskResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error=str(e),
            )


def create_agent(
    agent_id: str,
    role: AgentRole,
    task_handler: Optional[Callable[[Task], Any]] = None,
    message_handler: Optional[Callable[[AgentMessage], None]] = None,
    **config_kwargs,
) -> Agent:
    """
    Factory function to create an agent.

    Args:
        agent_id: Unique identifier for the agent
        role: The agent's role
        task_handler: Optional handler for processing tasks
        message_handler: Optional handler for processing messages
        **config_kwargs: Additional configuration options

    Returns:
        A new Agent instance
    """
    config = AgentConfig(agent_id=agent_id, role=role.name, **config_kwargs)

    if task_handler:
        return TaskAgent(config, role, task_handler, message_handler)
    else:
        return Agent(config, role, message_handler)
