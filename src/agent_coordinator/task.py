"""
Task module - Defines Task, TaskStatus, and TaskResult classes.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


class TaskStatus(str, Enum):
    """Possible states for a task."""
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(int, Enum):
    """Task priority levels."""
    CRITICAL = 0
    HIGH = 25
    MEDIUM = 50
    LOW = 75
    BACKGROUND = 100


@dataclass
class Task:
    """
    Represents a unit of work to be executed by an agent.

    Tasks can have:
    - Required capabilities that agents must have
    - Priority for scheduling
    - Timeout for execution
    - Dependencies on other tasks
    - Custom metadata
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = TaskPriority.MEDIUM
    timeout: float = 300.0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    # Runtime fields (not included in equality)
    status: TaskStatus = field(default=TaskStatus.PENDING, compare=False)
    assigned_agent: Optional[str] = field(default=None, compare=False)
    started_at: Optional[datetime] = field(default=None, compare=False)
    completed_at: Optional[datetime] = field(default=None, compare=False)
    retry_count: int = field(default=0, compare=False)

    @property
    def age_seconds(self) -> float:
        """Get task age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get task execution duration if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def can_be_assigned_to(self, agent_capabilities: List[str]) -> bool:
        """Check if task can be assigned to an agent with given capabilities."""
        if not self.required_capabilities:
            return True
        return all(cap in agent_capabilities for cap in self.required_capabilities)

    def with_dependency(self, task_id: str) -> "Task":
        """Add a dependency and return self for chaining."""
        if task_id not in self.dependencies:
            self.dependencies.append(task_id)
        return self

    def with_capability(self, capability: str) -> "Task":
        """Add a required capability and return self for chaining."""
        if capability not in self.required_capabilities:
            self.required_capabilities.append(capability)
        return self

    def with_metadata(self, key: str, value: Any) -> "Task":
        """Add metadata and return self for chaining."""
        self.metadata[key] = value
        return self


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    agent_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    completed_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "completed_at": self.completed_at.isoformat(),
            "execution_time": self.execution_time,
        }


@dataclass
class TaskExecution:
    """Tracks a task's execution lifecycle."""
    task: Task
    attempts: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.task.id

    def add_attempt(self, agent_id: str, started_at: datetime, result: Optional[TaskResult] = None) -> None:
        """Record an execution attempt."""
        self.task.retry_count = len(self.attempts)
        self.attempts.append({
            "agent_id": agent_id,
            "started_at": started_at,
            "result": result,
        })

    def get_last_attempt(self) -> Optional[Dict[str, Any]]:
        """Get the most recent attempt."""
        return self.attempts[-1] if self.attempts else None


class TaskBuilder:
    """Builder for creating tasks with a fluent API."""

    def __init__(self, description: str = ""):
        self._task = Task(description=description)

    def with_id(self, task_id: str) -> "TaskBuilder":
        """Set a custom task ID."""
        self._task.id = task_id
        return self

    def with_description(self, description: str) -> "TaskBuilder":
        """Set task description."""
        self._task.description = description
        return self

    def require_capability(self, capability: str) -> "TaskBuilder":
        """Add a required capability."""
        self._task.required_capabilities.append(capability)
        return self

    def require_capabilities(self, capabilities: List[str]) -> "TaskBuilder":
        """Add multiple required capabilities."""
        self._task.required_capabilities.extend(capabilities)
        return self

    def with_payload(self, payload: Dict[str, Any]) -> "TaskBuilder":
        """Set task payload."""
        self._task.payload = payload
        return self

    def with_priority(self, priority: TaskPriority) -> "TaskBuilder":
        """Set task priority."""
        self._task.priority = priority.value
        return self

    def with_timeout(self, timeout: float) -> "TaskBuilder":
        """Set task timeout in seconds."""
        self._task.timeout = timeout
        return self

    def with_max_retries(self, max_retries: int) -> "TaskBuilder":
        """Set maximum retry attempts."""
        self._task.max_retries = max_retries
        return self

    def with_dependency(self, task_id: str) -> "TaskBuilder":
        """Add a task dependency."""
        self._task.dependencies.append(task_id)
        return self

    def with_metadata(self, key: str, value: Any) -> "TaskBuilder":
        """Add metadata."""
        self._task.metadata[key] = value
        return self

    def build(self) -> Task:
        """Build and return the task."""
        return self._task


def create_task(
    description: str = "",
    capabilities: List[str] = None,
    payload: Dict[str, Any] = None,
    priority: TaskPriority = TaskPriority.MEDIUM,
    **kwargs,
) -> Task:
    """
    Factory function to create a task.

    Args:
        description: Task description
        capabilities: Required agent capabilities
        payload: Task payload data
        priority: Task priority
        **kwargs: Additional task attributes

    Returns:
        A new Task instance
    """
    return Task(
        description=description,
        required_capabilities=capabilities or [],
        payload=payload or {},
        priority=priority.value,
        **kwargs,
    )
