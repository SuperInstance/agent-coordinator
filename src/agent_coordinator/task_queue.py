"""
Task Queue - Manages task distribution and scheduling.
"""

import asyncio
import heapq
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging

from agent_coordinator.task import Task, TaskStatus, TaskResult
from agent_coordinator.agent import Agent

logger = logging.getLogger(__name__)


@dataclass
class PrioritizedTask:
    """A task with its priority for queue ordering."""
    task: Task
    priority: int
    created_at: datetime = field(default_factory=datetime.now)

    def __lt__(self, other: "PrioritizedTask") -> bool:
        # Lower priority value = higher priority
        if self.priority != other.priority:
            return self.priority < other.priority
        # Tie-break by creation time
        return self.created_at < other.created_at


@dataclass
class TaskAssignment:
    """Represents an assignment of a task to an agent."""
    task_id: str
    agent_id: str
    assigned_at: datetime = field(default_factory=datetime.now)
    completed: bool = False
    result: Optional[TaskResult] = None


class LoadBalancingStrategy(str):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    CAPABILITY_MATCH = "capability_match"
    RANDOM = "random"


class TaskQueue:
    """
    Manages task queue and distribution to agents.

    Features:
    - Priority-based task queue
    - Multiple load balancing strategies
    - Task tracking and history
    - Assignment and retry logic
    """

    def __init__(self, load_balancing: str = LoadBalancingStrategy.LEAST_LOADED):
        self._queue: List[PrioritizedTask] = []
        self._queue_lock = asyncio.Lock()

        # Task tracking
        self._pending_tasks: Dict[str, Task] = {}
        self._assigned_tasks: Dict[str, TaskAssignment] = {}
        self._completed_tasks: Dict[str, TaskResult] = {}

        # Load balancing
        self._load_balancing = load_balancing
        self._round_robin_index = 0

        # Callbacks
        self._on_task_queued: List[Callable[[Task], None]] = []
        self._on_task_assigned: List[Callable[[Task, str], None]] = []
        self._on_task_completed: List[Callable[[TaskResult], None]] = []
        self._on_task_failed: List[Callable[[Task, str], None]] = []

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def pending_count(self) -> int:
        return len(self._pending_tasks)

    @property
    def assigned_count(self) -> int:
        return len(self._assigned_tasks)

    @property
    def completed_count(self) -> int:
        return len(self._completed_tasks)

    def set_load_balancing(self, strategy: str) -> None:
        """Set the load balancing strategy."""
        self._load_balancing = strategy
        logger.info(f"Load balancing strategy set to: {strategy}")

    def add_queued_callback(self, callback: Callable[[Task], None]) -> None:
        self._on_task_queued.append(callback)

    def add_assigned_callback(self, callback: Callable[[Task, str], None]) -> None:
        self._on_task_assigned.append(callback)

    def add_completed_callback(self, callback: Callable[[TaskResult], None]) -> None:
        self._on_task_completed.append(callback)

    def add_failed_callback(self, callback: Callable[[Task, str], None]) -> None:
        self._on_task_failed.append(callback)

    async def enqueue(self, task: Task) -> None:
        """Add a task to the queue."""
        async with self._queue_lock:
            task.status = TaskStatus.QUEUED
            self._pending_tasks[task.id] = task

            prioritized = PrioritizedTask(task=task, priority=task.priority)
            heapq.heappush(self._queue, prioritized)

            logger.debug(f"Task {task.id} enqueued (priority: {task.priority})")

            # Notify callbacks
            for callback in self._on_task_queued:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(task)
                    else:
                        callback(task)
                except Exception as e:
                    logger.error(f"Queued callback error: {e}")

    async def dequeue(self) -> Optional[Task]:
        """Get the next task from the queue."""
        async with self._queue_lock:
            if not self._queue:
                return None

            prioritized = heapq.heappop(self._queue)
            task = prioritized.task

            self._pending_tasks.pop(task.id, None)
            return task

    async def peek(self) -> Optional[Task]:
        """Look at the next task without removing it."""
        async with self._queue_lock:
            if not self._queue:
                return None
            return self._queue[0].task

    async def assign(
        self,
        task: Task,
        agent_id: str,
        get_agent: Callable[[str], Optional[Agent]],
    ) -> bool:
        """
        Assign a task to an agent.

        Args:
            task: The task to assign
            agent_id: The agent to assign to
            get_agent: Function to get agent by ID

        Returns:
            True if assignment succeeded
        """
        agent = get_agent(agent_id)
        if agent is None:
            logger.error(f"Agent {agent_id} not found for task {task.id}")
            return False

        if not agent.is_available:
            logger.warning(f"Agent {agent_id} is not available for task {task.id}")
            return False

        # Create assignment
        self._assigned_tasks[task.id] = TaskAssignment(
            task_id=task.id,
            agent_id=agent_id,
        )
        task.status = TaskStatus.ASSIGNED
        task.assigned_agent = agent_id

        # Submit to agent
        await agent.submit_task(task)

        logger.info(f"Task {task.id} assigned to agent {agent_id}")

        # Notify callbacks
        for callback in self._on_task_assigned:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task, agent_id)
                else:
                    callback(task, agent_id)
            except Exception as e:
                logger.error(f"Assigned callback error: {e}")

        return True

    def mark_complete(self, result: TaskResult) -> None:
        """Mark a task as completed with its result."""
        task_id = result.task_id

        # Remove from assigned
        assignment = self._assigned_tasks.pop(task_id, None)
        if assignment:
            assignment.completed = True
            assignment.result = result

        # Store result
        self._completed_tasks[task_id] = result

        logger.debug(f"Task {task_id} marked complete (success: {result.success})")

        # Notify callbacks
        if result.success:
            for callback in self._on_task_completed:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Completed callback error: {e}")
        else:
            task = Task(
                id=task_id,
                description="",
            )
            for callback in self._on_task_failed:
                try:
                    callback(task, result.error or "Unknown error")
                except Exception as e:
                    logger.error(f"Failed callback error: {e}")

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a task."""
        if task_id in self._pending_tasks:
            return self._pending_tasks[task_id].status
        if task_id in self._assigned_tasks:
            return TaskStatus.RUNNING
        if task_id in self._completed_tasks:
            result = self._completed_tasks[task_id]
            return TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        return None

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a completed task."""
        return self._completed_tasks.get(task_id)

    def get_assignment(self, task_id: str) -> Optional[TaskAssignment]:
        """Get the assignment details for a task."""
        return self._assigned_tasks.get(task_id)

    async def select_agent(
        self,
        task: Task,
        available_agents: List[Agent],
    ) -> Optional[Agent]:
        """
        Select the best agent for a task using the configured strategy.

        Args:
            task: The task to assign
            available_agents: List of available agents

        Returns:
            The selected agent or None
        """
        if not available_agents:
            return None

        # Filter by capabilities
        capable = [
            a for a in available_agents
            if task.can_be_assigned_to(a.capabilities)
        ]

        if not capable:
            return None

        if self._load_balancing == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(capable)

        elif self._load_balancing == LoadBalancingStrategy.LEAST_LOADED:
            return self._select_least_loaded(capable)

        elif self._load_balancing == LoadBalancingStrategy.CAPABILITY_MATCH:
            return self._select_capability_match(task, capable)

        elif self._load_balancing == LoadBalancingStrategy.RANDOM:
            import random
            return random.choice(capable)

        # Default to least loaded
        return self._select_least_loaded(capable)

    def _select_round_robin(self, agents: List[Agent]) -> Agent:
        """Select agent using round-robin strategy."""
        agent = agents[self._round_robin_index % len(agents)]
        self._round_robin_index += 1
        return agent

    def _select_least_loaded(self, agents: List[Agent]) -> Agent:
        """Select agent with the fewest current tasks."""
        return min(agents, key=lambda a: a.current_task_count)

    def _select_capability_match(self, task: Task, agents: List[Agent]) -> Agent:
        """Select agent with best capability match."""
        if not task.required_capabilities:
            return self._select_least_loaded(agents)

        # Prefer agents with capabilities closer to requirements
        def score(agent: Agent) -> int:
            exact_match = len(set(task.required_capabilities) & set(agent.capabilities))
            return -exact_match  # Negative because we want max

        return min(agents, key=score)

    async def process_queue(
        self,
        get_available_agents: Callable[[], List[Agent]],
        get_agent: Callable[[str], Optional[Agent]],
    ) -> None:
        """
        Process the queue, assigning tasks to available agents.

        Args:
            get_available_agents: Function to get available agents
            get_agent: Function to get agent by ID
        """
        while self._queue:
            # Peek at next task
            task = await self.peek()
            if task is None:
                break

            # Get available agents
            available = get_available_agents()

            # Select best agent
            agent = await self.select_agent(task, available)

            if agent is None:
                # No suitable agent available, wait
                break

            # Dequeue and assign
            await self.dequeue()
            success = await self.assign(task, agent.id, get_agent)

            if not success:
                # Put task back if assignment failed
                await self.enqueue(task)
                break

    def get_statistics(self) -> Dict[str, any]:
        """Get queue statistics."""
        return {
            "queue_size": self.queue_size,
            "pending": self.pending_count,
            "assigned": self.assigned_count,
            "completed": self.completed_count,
            "load_balancing": self._load_balancing,
        }

    def get_history(self, limit: int = 100) -> List[TaskResult]:
        """Get recent task results."""
        results = list(self._completed_tasks.values())
        results.sort(key=lambda r: r.completed_at, reverse=True)
        return results[:limit]

    async def clear(self) -> None:
        """Clear all pending tasks."""
        async with self._queue_lock:
            self._queue.clear()
            self._pending_tasks.clear()
            logger.info("Task queue cleared")

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        async with self._queue_lock:
            # Remove from queue if pending
            self._queue = [pt for pt in self._queue if pt.task.id != task_id]
            heapq.heapify(self._queue)

            # Remove from pending
            if task_id in self._pending_tasks:
                task = self._pending_tasks.pop(task_id)
                task.status = TaskStatus.CANCELLED
                logger.info(f"Task {task_id} cancelled")
                return True

            return False
