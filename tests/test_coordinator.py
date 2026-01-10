"""Tests for AgentCoordinator."""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_coordinator import (
    AgentCoordinator,
    AgentRole,
    AgentState,
    Task,
    create_task,
    TaskStatus,
)


@pytest.fixture
async def coordinator():
    """Create a coordinator for testing."""
    coord = AgentCoordinator(name="test-coordinator")
    await coord.start()
    yield coord
    await coord.shutdown()


@pytest.mark.asyncio
async def test_coordinator_creation(coordinator):
    """Test coordinator creation and startup."""
    assert coordinator.is_running
    assert coordinator.name == "test-coordinator"


@pytest.mark.asyncio
async def test_role_registration(coordinator):
    """Test role registration."""
    role = AgentRole(name="test-role", capabilities=["test", "example"])
    await coordinator.register_role(role)

    retrieved = coordinator._registry.get_role("test-role")
    assert retrieved is not None
    assert retrieved.name == "test-role"
    assert "test" in retrieved.capabilities


@pytest.mark.asyncio
async def test_agent_spawn(coordinator):
    """Test agent spawning."""
    role = AgentRole(name="worker", capabilities=["work"])
    await coordinator.register_role(role)

    async def dummy_handler(task):
        return {"done": True}

    agent = await coordinator.spawn_agent(
        "test-agent",
        role="worker",
        task_handler=dummy_handler,
    )

    assert agent is not None
    assert agent.id == "test-agent"
    assert agent.role.name == "worker"


@pytest.mark.asyncio
async def test_task_submission(coordinator):
    """Test task submission and execution."""
    role = AgentRole(name="worker", capabilities=["process"])
    await coordinator.register_role(role)

    async def handler(task):
        return {"processed": task.payload.get("data")}

    await coordinator.spawn_agent(
        "worker-1",
        role="worker",
        task_handler=handler,
    )

    task = create_task(
        description="Test task",
        capabilities=["process"],
        payload={"data": "test-data"},
    )

    result = await coordinator.submit_task(task, wait_for_completion=True)

    assert result is not None
    assert result.success
    assert result.result.get("processed") == "test-data"


@pytest.mark.asyncio
async def test_multiple_agents(coordinator):
    """Test multiple agents with load balancing."""
    role = AgentRole(name="worker", capabilities=["work"])
    await coordinator.register_role(role)

    execution_counts = {"worker-1": 0, "worker-2": 0}

    async def make_handler(agent_id):
        async def handler(task):
            execution_counts[agent_id] += 1
            return {"agent": agent_id}
        return handler

    await coordinator.spawn_agent("worker-1", role="worker", task_handler=await make_handler("worker-1"))
    await coordinator.spawn_agent("worker-2", role="worker", task_handler=await make_handler("worker-2"))

    # Submit multiple tasks
    tasks = [
        create_task(f"Task {i}", capabilities=["work"])
        for i in range(10)
    ]

    await coordinator.submit_tasks(tasks, wait_for_all=True)

    # Both agents should have processed some tasks
    assert execution_counts["worker-1"] > 0
    assert execution_counts["worker-2"] > 0
    assert sum(execution_counts.values()) == 10


@pytest.mark.asyncio
async def test_get_status(coordinator):
    """Test getting coordinator status."""
    status = await coordinator.get_status()

    assert "name" in status
    assert "running" in status
    assert "agents" in status
    assert "tasks" in status
    assert "health" in status
    assert "metrics" in status


@pytest.mark.asyncio
async def test_agent_termination(coordinator):
    """Test agent termination."""
    role = AgentRole(name="worker", capabilities=["work"])
    await coordinator.register_role(role)

    await coordinator.spawn_agent("temp-agent", role="worker")

    assert coordinator._registry.exists("temp-agent")

    await coordinator.terminate_agent("temp-agent")

    assert not coordinator._registry.exists("temp-agent")
