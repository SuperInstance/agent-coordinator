"""Tests for Task and TaskQueue."""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_coordinator import (
    Task,
    TaskStatus,
    TaskResult,
    TaskPriority,
    TaskBuilder,
    create_task,
    TaskQueue,
)


def test_task_creation():
    """Test creating a task."""
    task = Task(
        description="Test task",
        required_capabilities=["test"],
        payload={"data": "value"},
    )

    assert task.description == "Test task"
    assert task.status == TaskStatus.PENDING
    assert task.required_capabilities == ["test"]
    assert task.payload["data"] == "value"


def test_task_builder():
    """Test the TaskBuilder fluent API."""
    task = (TaskBuilder("Complex task")
            .with_capability("compute")
            .with_capability("storage")
            .with_payload({"input": 42})
            .with_priority(TaskPriority.HIGH)
            .with_timeout(600)
            .build())

    assert task.description == "Complex task"
    assert "compute" in task.required_capabilities
    assert "storage" in task.required_capabilities
    assert task.priority == TaskPriority.HIGH.value
    assert task.timeout == 600


def test_task_factory():
    """Test the create_task factory function."""
    task = create_task(
        description="Factory task",
        capabilities=["test"],
        payload={"key": "value"},
        priority=TaskPriority.CRITICAL,
    )

    assert task.description == "Factory task"
    assert "test" in task.required_capabilities
    assert task.priority == TaskPriority.CRITICAL.value


def test_task_result():
    """Test TaskResult creation."""
    result = TaskResult(
        task_id="task-1",
        agent_id="agent-1",
        success=True,
        result={"output": "done"},
    )

    assert result.task_id == "task-1"
    assert result.agent_id == "agent-1"
    assert result.success
    assert result.result["output"] == "done"


def test_task_dependencies():
    """Test task with dependencies."""
    task = Task(description="Dependent task")
    task.with_dependency("task-1")
    task.with_dependency("task-2")

    assert "task-1" in task.dependencies
    assert "task-2" in task.dependencies


def test_task_can_be_assigned():
    """Test task capability matching."""
    task = Task(
        required_capabilities=["compute", "storage"],
    )

    assert task.can_be_assigned_to(["compute", "storage", "network"])
    assert task.can_be_assigned_to(["compute", "storage"])
    assert not task.can_be_assigned_to(["compute"])
    assert not task.can_be_assigned_to([])


@pytest.mark.asyncio
async def test_task_queue_enqueue():
    """Test enqueuing tasks."""
    queue = TaskQueue()

    task1 = Task(description="Task 1", priority=TaskPriority.HIGH.value)
    task2 = Task(description="Task 2", priority=TaskPriority.LOW.value)

    await queue.enqueue(task1)
    await queue.enqueue(task2)

    assert queue.queue_size == 2


@pytest.mark.asyncio
async def test_task_queue_dequeue():
    """Test dequeuing tasks with priority."""
    queue = TaskQueue()

    low_task = Task(description="Low", priority=TaskPriority.LOW.value)
    high_task = Task(description="High", priority=TaskPriority.HIGH.value)

    await queue.enqueue(low_task)
    await queue.enqueue(high_task)

    # High priority should come first
    first = await queue.dequeue()
    assert first.priority == TaskPriority.HIGH.value

    second = await queue.dequeue()
    assert second.priority == TaskPriority.LOW.value


@pytest.mark.asyncio
async def test_task_queue_mark_complete():
    """Test marking tasks complete."""
    queue = TaskQueue()

    result = TaskResult(
        task_id="task-1",
        agent_id="agent-1",
        success=True,
    )

    queue.mark_complete(result)

    status = queue.get_task_status("task-1")
    assert status == TaskStatus.COMPLETED

    retrieved = queue.get_task_result("task-1")
    assert retrieved is not None
    assert retrieved.task_id == "task-1"
